from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Devoto,
    EventoAgenda,
    Hermandad,
    ImagenHermandad,
    MarchaProcesional,
    TurnoRecorrido,
    VideoHermandad,
)


@admin.register(Hermandad)
class HermandadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "templo", "ciudad", "activa", "gps_activo", "traccar_device_id", "editor_turnos_link")
    list_filter = ("activa", "gps_activo", "ciudad")
    search_fields = ("nombre", "templo", "ciudad")
    prepopulated_fields = {"slug": ("nombre",)}
    fieldsets = (
        ("Identidad", {"fields": ("nombre", "slug", "templo", "ciudad", "descripcion_corta", "activa")}),
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
    list_display = ("nombre_completo", "dpi_mascarado", "hermandad", "correo", "celular", "creado_en")
    list_filter = ("hermandad", "departamento", "creado_en")
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
    readonly_fields = ("comprobante_codigo", "creado_en", "actualizado_en")
    date_hierarchy = "creado_en"
    ordering = ("-creado_en",)
    list_per_page = 50
    fieldsets = (
        ("Organización", {"fields": ("hermandad",)}),
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
        ("Medición", {"fields": ("medida_hombro_cm",)}),
        ("Privacidad y auditoría", {"fields": ("acepta_privacidad", "comprobante_codigo", "creado_en", "actualizado_en")}),
    )

    @admin.display(description="DPI")
    def dpi_mascarado(self, obj):
        return obj.dpi_mascarado

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
