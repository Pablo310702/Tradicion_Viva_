from io import BytesIO
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
import uuid
from django.urls import reverse


def _color_is_light(value: str) -> bool:
    """Return whether a hexadecimal color needs dark foreground text."""
    color = (value or "").strip().lstrip("#")
    if len(color) == 3:
        color = "".join(char * 2 for char in color)
    if len(color) != 6:
        return False
    try:
        red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return False
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return luminance >= 0.58

from .validators import (
    validate_audio_size,
    validate_image_size,
    validate_organization_media_quota,
    validate_video_size,
)


class OrganizationMediaQuotaMixin:
    media_file_fields = ()

    def save(self, *args, **kwargs):
        previous = None
        if not self._state.adding:
            previous = (
                type(self).objects.filter(pk=self.pk)
                .values(*self.media_file_fields)
                .first()
            )

        incoming_bytes = 0
        replaced_names = []
        for field_name in self.media_file_fields:
            uploaded_file = getattr(self, field_name, None)
            if uploaded_file and not getattr(uploaded_file, "_committed", True):
                incoming_bytes += uploaded_file.size
                old_name = (previous or {}).get(field_name)
                if old_name:
                    replaced_names.append(old_name)

        organization = getattr(self, "hermandad", self)
        if incoming_bytes:
            validate_organization_media_quota(
                organization,
                incoming_bytes,
                replaced_names,
            )
        return super().save(*args, **kwargs)


class Hermandad(OrganizationMediaQuotaMixin, models.Model):
    media_file_fields = ("imagen_templo", "logo", "portada")

    nombre = models.CharField(max_length=200)
    templo = models.CharField(max_length=200, blank=True)
    ciudad = models.CharField(max_length=100, default="Antigua Guatemala")
    slug = models.SlugField(max_length=80, unique=True)
    descripcion_corta = models.CharField(max_length=255, blank=True)
    ruta_trazado = models.JSONField(
        default=list,
        blank=True,
        verbose_name="trazado editable del recorrido",
    )
    turno_cambio_direccion = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="turno donde cambia de ida a vuelta",
    )
    ultima_posicion_turno_procesada_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="última posición GPS procesada para los turnos",
    )
    gps_ultimo_turno_en_zona_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="último turno cuya zona GPS se visitó",
    )

    TIPO_HERMANDAD = "hermandad"
    TIPO_COFRADIA = "cofradia"
    TIPO_CHOICES = [
        (TIPO_HERMANDAD, "Hermandad"),
        (TIPO_COFRADIA, "Cofradía"),
    ]
    tipo_organizacion = models.CharField(
        max_length=12,
        choices=TIPO_CHOICES,
        default=TIPO_HERMANDAD,
        verbose_name="tipo de organización",
    )

    mision = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    informacion_templo = models.TextField(blank=True)
    imagen_templo = models.ImageField(upload_to='templos/', blank=True, null=True, verbose_name='Imagen del templo')
    color_primario = models.CharField(max_length=20, default="#111111")
    color_acento = models.CharField(max_length=20, default="#b08d57")

    @property
    def color_primario_texto(self):
        return "#111111" if _color_is_light(self.color_primario) else "#ffffff"

    @property
    def color_acento_texto(self):
        return "#111111" if _color_is_light(self.color_acento) else "#ffffff"

    logo = models.ImageField(
        upload_to="logos/",
        null=True,
        blank=True,
        validators=[validate_image_size, FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    portada = models.ImageField(
        upload_to="portadas/",
        null=True,
        blank=True,
        validators=[validate_image_size, FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    almacenamiento_cuota_mb = models.PositiveIntegerField(
        default=2048,
        verbose_name="cuota de archivos (MB)",
        help_text="Límite total de fotos, videos, audio, logo y portada de esta organización.",
    )

    email_contacto = models.EmailField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)

    activa = models.BooleanField(default=True)

    # Seguimiento GPS dinámico. El servidor y las credenciales de Traccar son
    # globales; cada hermandad únicamente guarda el dispositivo que le
    # corresponde. Así las organizaciones nuevas no requieren cambios de código.
    gps_activo = models.BooleanField(
        default=False,
        verbose_name="seguimiento GPS activo",
        help_text="Activa el seguimiento en vivo para esta hermandad o cofradía.",
    )
    gps_publico = models.BooleanField(
        default=False,
        verbose_name="publicar seguimiento GPS",
        help_text="Permite mostrar la ubicación pública durante el intervalo configurado.",
    )
    gps_publicacion_desde = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="publicar desde",
    )
    gps_publicacion_hasta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="publicar hasta",
    )
    traccar_device_id = models.CharField(
        max_length=80,
        null=True,
        blank=True,
        verbose_name="identificador del dispositivo Traccar",
        help_text=(
            "Identificador que muestra Traccar Client (por ejemplo, 81709810). "
            "No es el ID interno de la base de datos de Traccar y puede compartirse entre varias organizaciones."
        ),
    )
    nombre_dispositivo_gps = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="nombre del dispositivo GPS",
        help_text="Nombre descriptivo opcional, por ejemplo: Teléfono procesión o Teltonika principal.",
    )

    def clean(self):
        super().clean()
        if self.gps_activo and not self.traccar_device_id:
            raise ValidationError(
                {"traccar_device_id": "Debes indicar el ID de Traccar para activar el seguimiento GPS."}
            )
        if self.gps_publico:
            if not self.gps_activo:
                raise ValidationError({"gps_publico": "Activa el seguimiento GPS antes de publicarlo."})
            if not self.gps_publicacion_desde or not self.gps_publicacion_hasta:
                raise ValidationError({"gps_publicacion_desde": "Define el inicio y el fin del horario público."})
        if bool(self.gps_publicacion_desde) != bool(self.gps_publicacion_hasta):
            raise ValidationError({"gps_publicacion_hasta": "Define ambas fechas para configurar el horario GPS."})
        if (
            self.gps_publicacion_desde
            and self.gps_publicacion_hasta
            and self.gps_publicacion_hasta <= self.gps_publicacion_desde
        ):
            raise ValidationError({"gps_publicacion_hasta": "El fin debe ser posterior al inicio."})

    @property
    def gps_configurado(self):
        return bool(self.gps_activo and self.traccar_device_id)

    @property
    def gps_publicable(self):
        if not (
            self.gps_configurado
            and self.gps_publico
            and self.gps_publicacion_desde
            and self.gps_publicacion_hasta
        ):
            return False
        from django.utils import timezone

        ahora = timezone.now()
        return self.gps_publicacion_desde <= ahora < self.gps_publicacion_hasta

    @property
    def es_hermandad(self):
        return self.tipo_organizacion == self.TIPO_HERMANDAD

    @property
    def es_cofradia(self):
        return self.tipo_organizacion == self.TIPO_COFRADIA

    @property
    def etiqueta_organizacion(self):
        return "Hermandad" if self.es_hermandad else "Cofradía"

    @property
    def etiqueta_musica(self):
        return "Marchas" if self.es_hermandad else "Repertorio de música festiva"

    class Meta:
        ordering = ["nombre"]
        verbose_name = "hermandad o cofradía"
        verbose_name_plural = "hermandades y cofradías"

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("web:hermandad_detalle", kwargs={"slug": self.slug})


class AdministradorOrganizacion(models.Model):
    """Asigna un usuario administrativo a una sola hermandad o cofradía.

    Los superusuarios conservan acceso global. Los usuarios administrativos
    normales quedan limitados a la organización indicada en esta asignación.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="asignacion_organizacion",
        verbose_name="usuario administrativo",
    )
    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="administradores_asignados",
        verbose_name="hermandad o cofradía",
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hermandad__nombre", "usuario__username"]
        verbose_name = "asignación de administrador"
        verbose_name_plural = "asignaciones de administradores"

    def __str__(self):
        return f"{self.usuario.get_username()} → {self.hermandad.nombre}"


class ActividadAdministrativa(models.Model):
    """Auditoría de acciones administrativas y cambios relevantes."""

    ACTIVIDAD = "actividad"
    CAMBIO_IMPORTANTE = "cambio_importante"
    TIPO_CHOICES = [
        (ACTIVIDAD, "Actividad administrativa"),
        (CAMBIO_IMPORTANTE, "Cambio importante"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_administrativas",
    )
    hermandad = models.ForeignKey(
        "Hermandad",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_administrativas",
    )
    tipo = models.CharField(max_length=24, choices=TIPO_CHOICES, default=ACTIVIDAD)
    accion = models.CharField(max_length=80)
    modelo = models.CharField(max_length=120, blank=True)
    objeto_id = models.CharField(max_length=80, blank=True)
    descripcion = models.TextField()
    detalles = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "actividad administrativa"
        verbose_name_plural = "actividades administrativas"
        indexes = [
            models.Index(fields=["tipo", "creado_en"], name="actividad_tipo_fecha_idx"),
            models.Index(fields=["hermandad", "creado_en"], name="actividad_org_fecha_idx"),
        ]

    def __str__(self):
        return f"{self.accion} · {self.descripcion[:60]}"


class TurnoRecorrido(models.Model):
    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="turnos_recorrido",
    )
    numero = models.PositiveIntegerField()
    nombre_turno = models.CharField(max_length=200)
    pieza = models.CharField(max_length=200)
    genero = models.CharField(max_length=100, blank=True)
    compositor = models.CharField(max_length=200, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    orden_ruta = models.PositiveIntegerField(default=0)
    activa = models.BooleanField(default=True)
    alcanzado_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="fecha y hora en que se alcanzó",
    )

    class Meta:
        ordering = ["numero", "orden_ruta"]
        constraints = [
            models.UniqueConstraint(
                fields=["hermandad", "numero", "orden_ruta"],
                name="turno_org_numero_orden_uniq",
            )
        ]

    def __str__(self):
        return f"{self.hermandad.nombre} - Turno {self.numero} - {self.pieza}"


class InscripcionTurno(models.Model):
    devoto = models.ForeignKey(
        "Devoto",
        on_delete=models.CASCADE,
        related_name="turnos_inscritos",
    )
    turno = models.ForeignKey(
        TurnoRecorrido,
        on_delete=models.PROTECT,
        related_name="inscripciones",
    )
    inscrito_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inscripciones_turnos_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    entregado = models.BooleanField(default=False)
    entregado_en = models.DateTimeField(null=True, blank=True)
    entregado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entregas_turnos_confirmadas",
    )

    class Meta:
        ordering = ["entregado", "-creado_en"]
        verbose_name = "inscripción de turno"
        verbose_name_plural = "inscripciones de turnos"
        constraints = [
            models.UniqueConstraint(
                fields=["devoto", "turno"],
                name="inscripcion_devoto_turno_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=["turno", "entregado"],
                name="ins_turno_entrega_idx",
            )
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.devoto_id and self.turno_id:
            if self.devoto.hermandad_id != self.turno.hermandad_id:
                raise ValidationError("El turno y el devoto deben pertenecer a la misma organización.")
        if self.entregado and not self.entregado_en:
            raise ValidationError({"entregado_en": "Indica cuándo se entregó el turno."})

    def __str__(self):
        return f"{self.devoto.nombre_completo} - Turno {self.turno.numero}"


class EventoAgenda(models.Model):
    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="eventos_agenda",
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    lugar = models.CharField(max_length=220, blank=True)
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    todo_el_dia = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["inicio", "titulo"]
        verbose_name = "evento de agenda"
        verbose_name_plural = "eventos de agenda"
        indexes = [models.Index(fields=["hermandad", "activo", "inicio"], name="agenda_org_act_inicio")]

    def clean(self):
        if self.fin and self.fin < self.inicio:
            raise ValidationError({"fin": "La fecha final no puede ser anterior al inicio."})

    def __str__(self):
        return f"{self.hermandad.nombre} - {self.titulo}"


class CuentaDevoto(models.Model):
    correo = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    ultimo_acceso = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["correo"]
        verbose_name = "cuenta de devoto"
        verbose_name_plural = "cuentas de devotos"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.correo


class SesionApiDevoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cuenta = models.ForeignKey(
        CuentaDevoto,
        on_delete=models.CASCADE,
        related_name="sesiones_api",
    )
    refresh_jti = models.CharField(max_length=64, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    revocado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["cuenta", "revocado_en"], name="api_sesion_cta_rev")]
        verbose_name = "sesión API de devoto"
        verbose_name_plural = "sesiones API de devotos"

    def __str__(self):
        return f"Sesión API de {self.cuenta.correo}"


class Devoto(models.Model):
    cuenta = models.ForeignKey(
        CuentaDevoto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inscripciones",
    )
    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="devotos",
    )
    dpi = models.CharField(
        max_length=13,
        validators=[RegexValidator(r"^\d{13}$", "El DPI debe contener exactamente 13 dígitos.")],
    )
    primer_nombre = models.CharField(max_length=80)
    otros_nombres = models.CharField(max_length=120, blank=True)
    primer_apellido = models.CharField(max_length=80)
    otros_apellidos = models.CharField(max_length=120, blank=True)
    fecha_nacimiento = models.DateField()
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    celular = models.CharField(
        max_length=20,
        validators=[RegexValidator(r"^[0-9+() -]{8,20}$", "Ingresa un número de celular válido.")],
    )
    correo = models.EmailField()
    medida_hombro_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    @property
    def medida_hombro_m(self):
        """Return the stored shoulder measurement in metres for display."""
        if self.medida_hombro_cm is None:
            return None
        return self.medida_hombro_cm / Decimal("100")

    @property
    def numero_registro(self):
        """Return the consecutive number of this devoto within its organization."""
        registros = type(self).objects.filter(hermandad_id=self.hermandad_id)
        if not self.pk:
            return registros.count() + 1

        return registros.filter(
            models.Q(creado_en__lt=self.creado_en)
            | models.Q(creado_en=self.creado_en, pk__lte=self.pk)
        ).count()

    comprobante_codigo = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    acepta_privacidad = models.BooleanField(default=False)
    acepta_comunicaciones = models.BooleanField(
        default=False,
        verbose_name="autoriza comunicaciones",
        help_text=(
            "Indicador general de que el devoto autorizó al menos un canal de comunicación. "
            "Se mantiene por compatibilidad con registros anteriores."
        ),
    )
    acepta_email = models.BooleanField(
        default=False,
        verbose_name="autoriza correo electrónico",
        help_text="Permite enviar avisos, saludos e información institucional por correo electrónico.",
    )
    acepta_sms = models.BooleanField(
        default=False,
        verbose_name="autoriza SMS",
        help_text="Permite enviar avisos, saludos e información institucional por mensaje SMS.",
    )
    acepta_whatsapp = models.BooleanField(
        default=False,
        verbose_name="autoriza WhatsApp",
        help_text="Permite enviar avisos, saludos e información institucional por WhatsApp.",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "devoto registrado"
        verbose_name_plural = "devotos registrados"
        constraints = [
            models.UniqueConstraint(
                fields=["hermandad", "dpi"],
                name="devoto_org_dpi_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["hermandad", "creado_en"], name="devoto_org_creado"),
            models.Index(fields=["correo"], name="devoto_correo_idx"),
        ]

    @property
    def nombre_completo(self):
        return " ".join(
            part
            for part in [
                self.primer_nombre,
                self.otros_nombres,
                self.primer_apellido,
                self.otros_apellidos,
            ]
            if part
        )

    @property
    def dpi_mascarado(self):
        return f"*********{self.dpi[-4:]}" if self.dpi else ""

    def __str__(self):
        return f"{self.nombre_completo} - {self.hermandad.nombre}"


class ImagenHermandad(OrganizationMediaQuotaMixin, models.Model):
    media_file_fields = ("imagen", "miniatura")

    CATEGORIA_CHOICES = [
        ("titular", "Nuestras imágenes"),
        ("galeria", "Galería de fotos"),
    ]

    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="imagenes",
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default="galeria")
    titulo = models.CharField(max_length=160)
    descripcion = models.TextField(blank=True)
    autor = models.CharField(
        max_length=180,
        blank=True,
        verbose_name="autor / fotografía",
        help_text="Crédito visible de la imagen, por ejemplo: Fotografía: Juan Pérez o Archivo Histórico.",
    )
    imagen = models.ImageField(
        upload_to="galeria/",
        validators=[validate_image_size, FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    miniatura = models.ImageField(upload_to="miniaturas/", blank=True, editable=False)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden", "titulo"]
        verbose_name = "imagen institucional"
        verbose_name_plural = "imágenes institucionales"
        indexes = [models.Index(fields=["hermandad", "categoria", "activo", "orden"], name="imagen_org_cat_act")]

    def __str__(self):
        return f"{self.hermandad.nombre} - {self.titulo}"

    def _crear_miniatura(self):
        from PIL import Image

        self.imagen.open("rb")
        with Image.open(self.imagen) as source:
            image = source.copy()
            image.thumbnail((900, 700), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "L"):
                background = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image)
                image = background
            elif image.mode == "L":
                image = image.convert("RGB")
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=84, optimize=True)
        filename = f"{Path(self.imagen.name).stem}_thumb.jpg"
        self.miniatura.save(filename, ContentFile(buffer.getvalue()), save=False)

    def save(self, *args, **kwargs):
        crear_miniatura = bool(self.imagen and not self.miniatura)
        super().save(*args, **kwargs)
        if crear_miniatura:
            self._crear_miniatura()
            super().save(update_fields=["miniatura"])


class VideoHermandad(OrganizationMediaQuotaMixin, models.Model):
    media_file_fields = ("video",)

    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    titulo = models.CharField(
        max_length=180
    )

    descripcion = models.TextField(
        blank=True
    )

    video = models.FileField(
        upload_to="videos/",
        blank=True,
        null=True,
        validators=[
            validate_video_size,
            FileExtensionValidator(
                ["mp4", "webm", "mov", "m4v"]
            ),
        ],
        verbose_name="archivo de video",
        help_text=(
            "Puedes subir un video directamente. "
            "Formatos permitidos: MP4, WEBM, MOV y M4V."
        ),
    )

    url = models.URLField(
        blank=True,
        help_text=(
            "Opcional. Enlace de YouTube o Vimeo. "
            "Utilízalo si no vas a subir un archivo de video."
        ),
    )

    orden = models.PositiveIntegerField(
        default=0
    )

    activo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["orden", "titulo"]
        verbose_name = "video institucional"
        verbose_name_plural = "videos institucionales"
        indexes = [
            models.Index(
                fields=[
                    "hermandad",
                    "activo",
                    "orden",
                ],
                name="video_org_act_orden",
            )
        ]

    def clean(self):
        super().clean()

        if not self.video and not self.url:
            raise ValidationError(
                "Debes subir un archivo de video o indicar un enlace de YouTube/Vimeo."
            )

    @property
    def embed_url(self):
        if not self.url:
            return ""

        parsed = urlparse(self.url)

        host = (
            parsed.netloc
            .lower()
            .removeprefix("www.")
        )

        if host == "youtu.be":
            video_id = (
                parsed.path
                .strip("/")
                .split("/")[0]
            )

            return (
                f"https://www.youtube-nocookie.com/embed/{video_id}"
                if video_id
                else ""
            )

        if host in {
            "youtube.com",
            "m.youtube.com",
        }:

            if parsed.path == "/watch":
                video_id = parse_qs(
                    parsed.query
                ).get("v", [""])[0]

            elif (
                parsed.path.startswith("/embed/")
                or parsed.path.startswith("/shorts/")
            ):
                video_id = (
                    parsed.path
                    .strip("/")
                    .split("/")[-1]
                )

            else:
                video_id = ""

            return (
                f"https://www.youtube-nocookie.com/embed/{video_id}"
                if video_id
                else ""
            )

        if host == "vimeo.com":
            video_id = (
                parsed.path
                .strip("/")
                .split("/")[0]
            )

            return (
                f"https://player.vimeo.com/video/{video_id}"
                if video_id.isdigit()
                else ""
            )

        return ""

    def __str__(self):
        return (
            f"{self.hermandad.nombre} - "
            f"{self.titulo}"
        )


class MarchaProcesional(OrganizationMediaQuotaMixin, models.Model):
    media_file_fields = ("audio",)

    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="marchas",
    )
    titulo = models.CharField(max_length=180)
    compositor = models.CharField(max_length=180, blank=True)
    descripcion = models.TextField(blank=True)
    audio = models.FileField(
        upload_to="marchas/",
        blank=True,
        validators=[validate_audio_size, FileExtensionValidator(["mp3", "m4a", "ogg", "wav"])],
    )
    enlace = models.URLField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "titulo"]
        verbose_name = "pieza musical"
        verbose_name_plural = "repertorio musical"
        indexes = [models.Index(fields=["hermandad", "activo", "orden"], name="marcha_org_act_orden")]

    def clean(self):
        if not self.audio and not self.enlace:
            raise ValidationError("Agrega un archivo de audio o un enlace externo.")

    def __str__(self):
        return f"{self.hermandad.nombre} - {self.titulo}"


class Comunicado(models.Model):
    WHATSAPP_MODO_PLANTILLA = "template"
    WHATSAPP_MODO_TEXTO = "text"
    WHATSAPP_MODO_CHOICES = [
        (WHATSAPP_MODO_PLANTILLA, "Plantilla aprobada por Meta (recomendado)"),
        (WHATSAPP_MODO_TEXTO, "Texto libre (solo dentro de la ventana permitida por WhatsApp)"),
    ]
    WHATSAPP_PARAM_NOMBRE_MENSAJE = "name_message"
    WHATSAPP_PARAM_MENSAJE = "message"
    WHATSAPP_PARAM_NINGUNO = "none"
    WHATSAPP_PARAM_CHOICES = [
        (WHATSAPP_PARAM_NOMBRE_MENSAJE, "2 variables: nombre + mensaje"),
        (WHATSAPP_PARAM_MENSAJE, "1 variable: mensaje"),
        (WHATSAPP_PARAM_NINGUNO, "Sin variables (por ejemplo, hello_world)"),
    ]

    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comunicados",
        help_text="Déjalo vacío para enviar a devotos autorizados de todas las organizaciones.",
    )
    asunto = models.CharField(max_length=180)
    mensaje = models.TextField(
        help_text=(
            "Puedes personalizar el contenido con {nombre}, {primer_nombre}, {organizacion}, "
            "{tipo_organizacion} y {asunto}."
        )
    )
    enviar_email = models.BooleanField(default=True, verbose_name="enviar por correo")
    enviar_sms = models.BooleanField(default=False, verbose_name="enviar por SMS")
    enviar_whatsapp = models.BooleanField(default=False, verbose_name="enviar por WhatsApp")
    whatsapp_modo = models.CharField(
        max_length=12,
        choices=WHATSAPP_MODO_CHOICES,
        default=WHATSAPP_MODO_PLANTILLA,
        verbose_name="modo de envío por WhatsApp",
    )
    whatsapp_template_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="nombre de plantilla de WhatsApp",
        help_text=(
            "Opcional. Si queda vacío se usa WHATSAPP_DEFAULT_TEMPLATE_NAME del archivo .env. "
            "La plantilla recomendada contiene dos variables de cuerpo: {{1}} nombre y {{2}} mensaje."
        ),
    )
    whatsapp_template_language = models.CharField(
        max_length=12,
        default="es",
        verbose_name="idioma de plantilla",
        help_text="Código de idioma aprobado en Meta, por ejemplo es, es_MX o en_US.",
    )
    whatsapp_template_param_mode = models.CharField(
        max_length=16,
        choices=WHATSAPP_PARAM_CHOICES,
        default=WHATSAPP_PARAM_NOMBRE_MENSAJE,
        verbose_name="variables de la plantilla",
        help_text=(
            "Selecciona cuántas variables de cuerpo espera la plantilla aprobada. "
            "Para la plantilla sugerida usa nombre + mensaje."
        ),
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    total_enviados = models.PositiveIntegerField(default=0, editable=False)
    total_fallidos = models.PositiveIntegerField(default=0, editable=False)
    total_email_enviados = models.PositiveIntegerField(default=0, editable=False)
    total_email_fallidos = models.PositiveIntegerField(default=0, editable=False)
    total_sms_enviados = models.PositiveIntegerField(default=0, editable=False)
    total_sms_fallidos = models.PositiveIntegerField(default=0, editable=False)
    total_whatsapp_enviados = models.PositiveIntegerField(default=0, editable=False)
    total_whatsapp_fallidos = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "comunicado masivo"
        verbose_name_plural = "comunicados masivos"

    @property
    def destinatarios_descripcion(self):
        return self.hermandad.nombre if self.hermandad else "Todas las organizaciones"

    @property
    def canales_descripcion(self):
        canales = []
        if self.enviar_email:
            canales.append("Correo")
        if self.enviar_sms:
            canales.append("SMS")
        if self.enviar_whatsapp:
            canales.append("WhatsApp")
        return ", ".join(canales) if canales else "Ninguno"

    def __str__(self):
        return self.asunto


class EnvioComunicado(models.Model):
    CANAL_EMAIL = "email"
    CANAL_SMS = "sms"
    CANAL_WHATSAPP = "whatsapp"
    CANAL_CHOICES = [
        (CANAL_EMAIL, "Correo electrónico"),
        (CANAL_SMS, "SMS"),
        (CANAL_WHATSAPP, "WhatsApp"),
    ]

    ESTADO_ACEPTADO = "aceptado"
    ESTADO_ENTREGADO = "entregado"
    ESTADO_FALLIDO = "fallido"
    ESTADO_OMITIDO = "omitido"
    ESTADO_CHOICES = [
        (ESTADO_ACEPTADO, "Aceptado por el proveedor"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_FALLIDO, "Fallido"),
        (ESTADO_OMITIDO, "Omitido"),
    ]

    comunicado = models.ForeignKey(
        Comunicado,
        on_delete=models.CASCADE,
        related_name="envios",
    )
    devoto = models.ForeignKey(
        Devoto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_comunicados",
    )
    canal = models.CharField(max_length=12, choices=CANAL_CHOICES)
    destinatario = models.CharField(max_length=254)
    proveedor = models.CharField(max_length=40, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_ACEPTADO)
    proveedor_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    proveedor_estado = models.CharField(max_length=80, blank=True)
    detalle_error = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "envío de comunicado"
        verbose_name_plural = "envíos de comunicados"
        indexes = [
            models.Index(fields=["comunicado", "canal", "estado"], name="envio_com_canal_estado"),
        ]

    def __str__(self):
        return f"{self.get_canal_display()} - {self.destinatario} - {self.get_estado_display()}"
