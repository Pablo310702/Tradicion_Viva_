from django.urls import path

from . import auth_api, views, webhooks

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("organizaciones/", views.organizaciones, name="organizaciones"),
    path("privacidad/", views.privacidad, name="privacidad"),
    path("politicas-de-calidad/", views.calidad, name="calidad"),
    path("iniciar-sesion/", views.iniciar_sesion, name="iniciar_sesion"),
    path("iniciar-sesion/devoto/", views.devoto_login, name="devoto_login"),
    path("iniciar-sesion/administrativo/", views.administrativo_login, name="administrativo_login"),
    path("administrativo/panel/", views.admin_dashboard, name="admin_dashboard"),
    path("api/auth/login/", auth_api.api_login, name="api_auth_login"),
    path("api/auth/refresh/", auth_api.api_refresh, name="api_auth_refresh"),
    path("api/auth/me/", auth_api.api_me, name="api_auth_me"),
    path("api/auth/logout/", auth_api.api_logout, name="api_auth_logout"),
    path("devoto/", views.devoto_panel, name="devoto_panel"),
    path(
        "devoto/preferencias-comunicacion/<int:devoto_id>/",
        views.devoto_preferencias_comunicacion,
        name="devoto_preferencias_comunicacion",
    ),
    path("devoto/cerrar-sesion/", views.devoto_logout, name="devoto_logout"),
    path("devoto/recuperar-contrasena/", views.devoto_password_reset, name="devoto_password_reset"),
    path(
        "devoto/restablecer-contrasena/<str:token>/",
        views.devoto_password_reset_confirm,
        name="devoto_password_reset_confirm",
    ),
    path("hermandad/<slug:slug>/", views.hermandad_detalle, name="hermandad_detalle"),
    path("hermandad/<slug:slug>/devoto/comprobante/<uuid:codigo>/", views.comprobante_devoto, name="comprobante_devoto"),
    path("devoto/qr/<uuid:codigo>/", views.qr_devoto, name="qr_devoto"),
    path(
        "hermandad/<slug:slug>/inscripciones-turnos/",
        views.inscripciones_turnos,
        name="inscripciones_turnos",
    ),
    path(
        "hermandad/<slug:slug>/inscripciones-turnos/entregar/<int:inscripcion_id>/",
        views.entregar_turno,
        name="entregar_turno",
    ),
    path(
        "hermandad/<slug:slug>/inscripciones-turnos/limpiar-entrega/<int:inscripcion_id>/",
        views.limpiar_entrega_turno,
        name="limpiar_entrega_turno",
    ),

    # Editor canónico para TODAS las hermandades/cofradías, incluidas las nuevas.
    # Estas rutas deben ir antes de la sección genérica para que "editor-turnos"
    # no sea interpretado como el nombre de una sección pública.
    path("hermandad/<slug:slug>/editor-turnos/", views.editor_turnos, name="editor_turnos"),
    path(
        "hermandad/<slug:slug>/editor-turnos/eliminar/<int:turno_id>/",
        views.eliminar_turno,
        name="eliminar_turno",
    ),

    path("hermandad/<slug:slug>/<slug:seccion>/", views.seccion_generica, name="seccion_generica"),
    path("<slug:slug>/seguimiento/", views.seguimiento, name="seguimiento"),
    path("api/<slug:slug>/ubicacion/", views.api_ubicacion, name="api_ubicacion"),
    path("robots.txt", views.robots_txt, name="robots_txt"),

    # Webhooks de estado de comunicaciones automáticas.
    path("webhooks/twilio/status/", webhooks.twilio_status_webhook, name="twilio_status_webhook"),
    path("webhooks/whatsapp/", webhooks.whatsapp_webhook, name="whatsapp_webhook"),

    # Compatibilidad con URLs antiguas del editor. No se usan para generar enlaces nuevos.
    path("<slug:slug>/editor-turnos/", views.editor_turnos, name="editor_turnos_legacy"),
    path(
        "<slug:slug>/editor-turnos/eliminar/<int:turno_id>/",
        views.eliminar_turno,
        name="eliminar_turno_legacy",
    ),

    # Direcciones antiguas conservadas para no romper enlaces existentes.
    path("san-jose/seguimiento-anterior/", views.seguimiento_san_jose, name="seguimiento_san_jose"),
    path("api/san-jose/ubicacion-anterior/", views.api_ubicacion_san_jose, name="api_ubicacion_san_jose"),
]
