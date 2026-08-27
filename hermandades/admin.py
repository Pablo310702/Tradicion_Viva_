from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Comunicado,
    CuentaDevoto,
    Devoto,
    EventoAgenda,
    EnvioComunicado,
    Hermandad,
    ImagenHermandad,
    MarchaProcesional,
    TurnoRecorrido,
    VideoHermandad,
)

from .messaging import MessagingError, enviar_comunicado


@admin.register(Hermandad)
class HermandadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo_organizacion", "templo", "ciudad", "activa", "gps_activo", "traccar_device_id", "editor_turnos_link")
    list_filter = ("tipo_organizacion", "activa", "gps_activo", "ciudad")
    search_fields = ("nombre", "templo", "ciudad")
    prepopulated_fields = {"slug": ("nombre",)}
    fieldsets = (
        ("Identidad", {"fields": ("nombre", "tipo_organizacion", "slug", "templo", "ciudad", "descripcion_corta", "activa")}),
        ("Contenido institucional", {"fields": ("mision", "vision", "informacion_templo")}),
        ("Diseño", {"fields": (("color_primario", "color_acento"), ("logo", "portada"))}),
        ("Contacto", {"fields": ("email_contacto", "facebook", "instagram")}),
        (
            "Seguimiento GPS / Traccar",
            {
                "fields": ("gps_activo", "traccar_device_id", "nombre_dispositivo_gps"),
                "description": (
                    "Activa el GPS y copia aquí el IDENTIFICADOR que aparece en Traccar Client (por ejemplo, 81709810). "
                    "El sistema buscará automáticamente el ID interno del dispositivo en Traccar. "
                    "El mismo identificador puede asignarse a varias hermandades o cofradías. "
                    "La URL, el usuario y la contraseña de la cuenta Traccar se configuran una sola vez en el archivo .env."
                ),
            },
        ),
    )

    @admin.display(description="Turnos")
    def editor_turnos_link(self, obj):
        if not obj or not obj.pk or not obj.slug:
            return "Guarda primero la organización"
        url = reverse("web:editor_turnos", kwargs={"slug": obj.slug})
        return format_html('<a class="button" href="{}">Abrir editor</a>', url)


@admin.register(TurnoRecorrido)
class TurnoRecorridoAdmin(admin.ModelAdmin):
    """Editor de turnos disponible únicamente para usuarios del administrador."""

    list_display = (
        "hermandad",
        "numero",
        "orden_ruta",
        "nombre_turno",
        "pieza",
        "direccion",
        "activa",
    )
    list_display_links = ("nombre_turno", "pieza")
    list_editable = ("numero", "orden_ruta", "activa")
    list_filter = ("hermandad", "activa", "genero")
    search_fields = ("nombre_turno", "pieza", "compositor", "direccion")
    ordering = ("hermandad", "orden_ruta", "numero")
    autocomplete_fields = ("hermandad",)
    list_per_page = 50

    fieldsets = (
        ("Organización y orden", {"fields": ("hermandad", "numero", "orden_ruta", "activa")}),
        ("Información del turno", {"fields": ("nombre_turno", "pieza", "genero", "compositor")}),
        (
            "Punto del recorrido",
            {
                "fields": ("direccion", ("latitud", "longitud")),
                "description": "Ingrese las coordenadas del punto exacto correspondiente al turno.",
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hermandad")


@admin.register(EventoAgenda)
class EventoAgendaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "hermandad", "inicio", "fin", "todo_el_dia", "activo")
    list_filter = ("hermandad", "activo", "todo_el_dia", "inicio")
    search_fields = ("titulo", "descripcion", "lugar", "hermandad__nombre")
    ordering = ("inicio", "hermandad")
    autocomplete_fields = ("hermandad",)
    date_hierarchy = "inicio"
    fieldsets = (
        ("Organización", {"fields": ("hermandad", "activo")}),
        ("Actividad", {"fields": ("titulo", "descripcion", "lugar")}),
        ("Fecha y horario", {"fields": (("inicio", "fin"), "todo_el_dia")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hermandad")


@admin.register(Devoto)
class DevotoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_completo", "dpi_mascarado", "hermandad", "correo", "celular",
        "acepta_email", "acepta_sms", "acepta_whatsapp", "creado_en"
    )
    list_filter = (
        "hermandad", "acepta_email", "acepta_sms", "acepta_whatsapp",
        "departamento", "creado_en"
    )
    search_fields = (
        "primer_nombre",
        "otros_nombres",
        "primer_apellido",
        "otros_apellidos",
        "dpi",
        "correo",
        "celular",
    )
    autocomplete_fields = ("hermandad",)
    readonly_fields = ("comprobante_codigo", "creado_en", "actualizado_en", "acepta_comunicaciones")
    date_hierarchy = "creado_en"
    ordering = ("-creado_en",)
    list_per_page = 50
    fieldsets = (
        ("Organización y cuenta", {"fields": ("hermandad", "cuenta")}),
        (
            "Identificación",
            {
                "fields": (
                    "dpi",
                    ("primer_nombre", "otros_nombres"),
                    ("primer_apellido", "otros_apellidos"),
                    "fecha_nacimiento",
                )
            },
        ),
        ("Ubicación y contacto", {"fields": (("departamento", "municipio"), ("celular", "correo"))}),
        ("Medición (solo hermandades)", {"fields": ("medida_hombro_cm",)}),
        (
            "Privacidad y comunicaciones",
            {
                "fields": (
                    "acepta_privacidad",
                    "acepta_comunicaciones",
                    "acepta_email",
                    "acepta_sms",
                    "acepta_whatsapp",
                ),
                "description": (
                    "Los envíos masivos respetan la autorización individual de cada canal. "
                    "El indicador general se conserva para compatibilidad con registros anteriores."
                ),
            },
        ),
        ("Auditoría", {"fields": ("comprobante_codigo", "creado_en", "actualizado_en")}),
    )

    @admin.display(description="DPI")
    def dpi_mascarado(self, obj):
        return obj.dpi_mascarado

    def save_model(self, request, obj, form, change):
        obj.acepta_comunicaciones = any([obj.acepta_email, obj.acepta_sms, obj.acepta_whatsapp])
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hermandad")


@admin.register(ImagenHermandad)
class ImagenHermandadAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "hermandad", "categoria", "orden", "activo")
    list_filter = ("hermandad", "categoria", "activo")
    search_fields = ("titulo", "autor", "descripcion", "hermandad__nombre")
    list_editable = ("orden", "activo")
    autocomplete_fields = ("hermandad",)
    readonly_fields = ("miniatura", "creado_en")
    fieldsets = (
        ("Organización y publicación", {"fields": ("hermandad", "categoria", ("orden", "activo"))}),
        ("Imagen", {"fields": ("titulo", "autor", "descripcion", "imagen", "miniatura")}),
        ("Auditoría", {"fields": ("creado_en",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hermandad")


@admin.register(VideoHermandad)
class VideoHermandadAdmin(admin.ModelAdmin):
    list_display = ("titulo", "hermandad", "orden", "activo")
    list_filter = ("hermandad", "activo")
    search_fields = ("titulo", "descripcion", "url", "hermandad__nombre")
    list_editable = ("orden", "activo")
    autocomplete_fields = ("hermandad",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hermandad")


@admin.register(MarchaProcesional)
class MarchaProcesionalAdmin(admin.ModelAdmin):
    list_display = ("titulo", "compositor", "hermandad", "orden", "activo")
    list_filter = ("hermandad", "activo")
    search_fields = ("titulo", "compositor", "descripcion", "hermandad__nombre")
    list_editable = ("orden", "activo")
    autocomplete_fields = ("hermandad",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hermandad")


@admin.register(CuentaDevoto)
class CuentaDevotoAdmin(admin.ModelAdmin):
    list_display = ("correo", "activa", "creado_en", "ultimo_acceso")
    list_filter = ("activa", "creado_en", "ultimo_acceso")
    search_fields = ("correo",)
    readonly_fields = ("password", "creado_en", "ultimo_acceso")
    fields = ("correo", "activa", "password", "creado_en", "ultimo_acceso")


class ComunicadoAdminForm(forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not any(
            [
                cleaned.get("enviar_email"),
                cleaned.get("enviar_sms"),
                cleaned.get("enviar_whatsapp"),
            ]
        ):
            raise forms.ValidationError("Selecciona al menos un canal de envío.")
        if cleaned.get("enviar_whatsapp") and cleaned.get("whatsapp_modo") == Comunicado.WHATSAPP_MODO_PLANTILLA:
            # El nombre puede venir del .env, por eso no se obliga aquí.
            language = (cleaned.get("whatsapp_template_language") or "").strip()
            if not language:
                self.add_error("whatsapp_template_language", "Indica el idioma de la plantilla aprobada en Meta.")
        return cleaned


@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    form = ComunicadoAdminForm
    list_display = (
        "asunto",
        "destinatarios_descripcion",
        "canales_descripcion",
        "creado_en",
        "enviado_en",
        "total_enviados",
        "total_fallidos",
    )
    list_filter = ("hermandad", "enviar_email", "enviar_sms", "enviar_whatsapp", "creado_en", "enviado_en")
    search_fields = ("asunto", "mensaje", "hermandad__nombre")
    readonly_fields = (
        "creado_en",
        "enviado_en",
        "total_enviados",
        "total_fallidos",
        "total_email_enviados",
        "total_email_fallidos",
        "total_sms_enviados",
        "total_sms_fallidos",
        "total_whatsapp_enviados",
        "total_whatsapp_fallidos",
    )
    actions = (
        "enviar_canales_seleccionados",
        "enviar_solo_correo",
        "enviar_solo_sms",
        "enviar_solo_whatsapp",
    )
    fieldsets = (
        (
            "Destinatarios",
            {
                "fields": ("hermandad",),
                "description": (
                    "Selecciona una organización o déjala vacía para enviar a todas. "
                    "Solo se contactará a devotos que hayan autorizado específicamente cada canal."
                ),
            },
        ),
        (
            "Canales",
            {
                "fields": (("enviar_email", "enviar_sms", "enviar_whatsapp"),),
                "description": "Marca los canales que deseas utilizar al ejecutar la acción 'Enviar por canales seleccionados'.",
            },
        ),
        (
            "Contenido",
            {
                "fields": ("asunto", "mensaje"),
                "description": (
                    "Marcadores disponibles: {nombre}, {primer_nombre}, {organizacion}, "
                    "{tipo_organizacion} y {asunto}."
                ),
            },
        ),
        (
            "WhatsApp Business Cloud API",
            {
                "fields": (
                    "whatsapp_modo",
                    "whatsapp_template_name",
                    "whatsapp_template_language",
                    "whatsapp_template_param_mode",
                ),
                "description": (
                    "Para avisos iniciados por la organización usa una plantilla aprobada por Meta. "
                    "La plantilla sugerida tiene dos variables en el cuerpo: {{1}} = nombre y {{2}} = mensaje. "
                    "El modo texto libre solo debe usarse cuando WhatsApp permita responder dentro de la ventana de conversación."
                ),
            },
        ),
        (
            "Resultado del último envío",
            {
                "fields": (
                    ("creado_en", "enviado_en"),
                    ("total_enviados", "total_fallidos"),
                    ("total_email_enviados", "total_email_fallidos"),
                    ("total_sms_enviados", "total_sms_fallidos"),
                    ("total_whatsapp_enviados", "total_whatsapp_fallidos"),
                )
            },
        ),
    )
    autocomplete_fields = ("hermandad",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hermandad")

    def _run_send(self, request, queryset, canales=None):
        for comunicado in queryset.select_related("hermandad"):
            try:
                stats = enviar_comunicado(comunicado, canales=canales)
            except MessagingError as exc:
                self.message_user(request, f"{comunicado.asunto}: {exc}", level=messages.ERROR)
                continue
            except Exception as exc:
                self.message_user(
                    request,
                    f"{comunicado.asunto}: ocurrió un error inesperado: {exc}",
                    level=messages.ERROR,
                )
                continue

            parts = []
            for channel, label in (("email", "correo"), ("sms", "SMS"), ("whatsapp", "WhatsApp")):
                values = stats[channel]
                if canales is None:
                    enabled = getattr(comunicado, f"enviar_{channel}")
                else:
                    enabled = channel in set(canales)
                if enabled:
                    parts.append(f"{label}: {values['enviados']} aceptados / {values['fallidos']} fallidos")

            level = messages.SUCCESS if comunicado.total_fallidos == 0 else messages.WARNING
            self.message_user(request, f"{comunicado.asunto} — " + "; ".join(parts), level=level)

    @admin.action(description="Enviar por los canales seleccionados en el comunicado")
    def enviar_canales_seleccionados(self, request, queryset):
        self._run_send(request, queryset)

    @admin.action(description="Enviar únicamente por correo electrónico")
    def enviar_solo_correo(self, request, queryset):
        self._run_send(request, queryset, canales={EnvioComunicado.CANAL_EMAIL})

    @admin.action(description="Enviar únicamente por SMS (Twilio)")
    def enviar_solo_sms(self, request, queryset):
        self._run_send(request, queryset, canales={EnvioComunicado.CANAL_SMS})

    @admin.action(description="Enviar únicamente por WhatsApp (Meta Cloud API)")
    def enviar_solo_whatsapp(self, request, queryset):
        self._run_send(request, queryset, canales={EnvioComunicado.CANAL_WHATSAPP})


@admin.register(EnvioComunicado)
class EnvioComunicadoAdmin(admin.ModelAdmin):
    list_display = (
        "creado_en",
        "comunicado",
        "canal",
        "destinatario",
        "proveedor",
        "estado",
        "proveedor_estado",
    )
    list_filter = ("canal", "estado", "proveedor", "creado_en")
    search_fields = (
        "comunicado__asunto",
        "destinatario",
        "proveedor_message_id",
        "devoto__primer_nombre",
        "devoto__primer_apellido",
    )
    readonly_fields = (
        "comunicado",
        "devoto",
        "canal",
        "destinatario",
        "proveedor",
        "estado",
        "proveedor_message_id",
        "proveedor_estado",
        "detalle_error",
        "creado_en",
        "actualizado_en",
    )
    ordering = ("-creado_en",)
    date_hierarchy = "creado_en"
    list_per_page = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("comunicado", "devoto")
