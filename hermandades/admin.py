from django.contrib import admin
from .models import Hermandad, TurnoRecorrido


@admin.register(Hermandad)
class HermandadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "templo", "ciudad", "activa")
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(TurnoRecorrido)
class TurnoRecorridoAdmin(admin.ModelAdmin):
    list_display = (
        "hermandad",
        "numero",
        "orden_ruta",
        "pieza",
        "genero",
        "compositor",
        "latitud",
        "longitud",
        "activa",
    )
    list_filter = ("hermandad", "activa", "numero")
    search_fields = ("pieza", "nombre_turno", "compositor", "direccion")