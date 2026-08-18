from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
import uuid
from django.urls import reverse

from .validators import validate_audio_size, validate_image_size


class Hermandad(models.Model):
    nombre = models.CharField(max_length=200)
    templo = models.CharField(max_length=200, blank=True)
    ciudad = models.CharField(max_length=100, default="Antigua Guatemala")
    slug = models.SlugField(max_length=80, unique=True)
    descripcion_corta = models.CharField(max_length=255, blank=True)

    mision = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    informacion_templo = models.TextField(blank=True)

    color_primario = models.CharField(max_length=20, default="#111111")
    color_acento = models.CharField(max_length=20, default="#b08d57")

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

    @property
    def gps_configurado(self):
        return bool(self.gps_activo and self.traccar_device_id)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "hermandad o cofradía"
        verbose_name_plural = "hermandades y cofradías"

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("web:hermandad_detalle", kwargs={"slug": self.slug})


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


class Devoto(models.Model):
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
    comprobante_codigo = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    acepta_privacidad = models.BooleanField(default=False)
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


class ImagenHermandad(models.Model):
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


class VideoHermandad(models.Model):
    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="videos",
    )
    titulo = models.CharField(max_length=180)
    descripcion = models.TextField(blank=True)
    url = models.URLField(help_text="Enlace de YouTube o Vimeo.")
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "titulo"]
        verbose_name = "video institucional"
        verbose_name_plural = "videos institucionales"
        indexes = [models.Index(fields=["hermandad", "activo", "orden"], name="video_org_act_orden")]

    @property
    def embed_url(self):
        parsed = urlparse(self.url)
        host = parsed.netloc.lower().removeprefix("www.")
        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]
            return f"https://www.youtube-nocookie.com/embed/{video_id}" if video_id else ""
        if host in {"youtube.com", "m.youtube.com"}:
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/"):
                video_id = parsed.path.strip("/").split("/")[-1]
            else:
                video_id = ""
            return f"https://www.youtube-nocookie.com/embed/{video_id}" if video_id else ""
        if host == "vimeo.com":
            video_id = parsed.path.strip("/").split("/")[0]
            return f"https://player.vimeo.com/video/{video_id}" if video_id.isdigit() else ""
        return ""

    def __str__(self):
        return f"{self.hermandad.nombre} - {self.titulo}"


class MarchaProcesional(models.Model):
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
        verbose_name = "marcha procesional"
        verbose_name_plural = "marchas procesionales"
        indexes = [models.Index(fields=["hermandad", "activo", "orden"], name="marcha_org_act_orden")]

    def clean(self):
        if not self.audio and not self.enlace:
            raise ValidationError("Agrega un archivo de audio o un enlace externo.")

    def __str__(self):
        return f"{self.hermandad.nombre} - {self.titulo}"
