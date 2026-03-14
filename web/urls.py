from django.urls import path
from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("hermandad/<slug:slug>/", views.hermandad_detalle, name="hermandad_detalle"),
    path("hermandad/<slug:slug>/<slug:seccion>/", views.seccion_generica, name="seccion_generica"),
    path("san-jose/seguimiento/", views.seguimiento_san_jose, name="seguimiento_san_jose"),
    path("san-jose/editor-turnos/", views.editor_turnos_san_jose, name="editor_turnos_san_jose"),
    path("san-jose/eliminar-turno/<int:turno_id>/", views.eliminar_turno_san_jose, name="eliminar_turno_san_jose"),
    path("api/san-jose/ubicacion/", views.api_ubicacion_san_jose, name="api_ubicacion_san_jose"),
]
