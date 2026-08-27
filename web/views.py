import calendar
import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_user_model, login
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from hermandades.models import CuentaDevoto, Devoto, EventoAgenda, Hermandad, TurnoRecorrido

from .forms import (
    AdministrativoLoginForm,
    DevotoForm,
    DevotoLoginForm,
    RecuperarCuentaDevotoForm,
    RestablecerPasswordDevotoForm,
)
from .pdf_utils import generar_comprobante_devoto

logger = logging.getLogger(__name__)

SECCION_TITULOS = {
    "mision-vision": "Misión y Visión",
    "nuestras-imagenes": "Nuestras Imágenes",
    "templo": "Templo",
    "agenda": "Agenda",
    "galeria-fotos": "Galería de fotos",
    "galeria-filmica": "Galería fílmica",
    "marchas": "Marchas",
    "registro-actualizacion-datos": "Registro",
}


# Alias históricos: se conservan únicamente para enlaces antiguos.
# El editor NO depende de esta lista: cualquier hermandad/cofradía nueva funciona
# automáticamente usando el slug guardado en la base de datos.
EDITOR_SLUG_ALIASES = {
    "lamerced": "rosario-merced",
    "la-merced": "rosario-merced",
    "jesus-sepultado": "hermandad-ci-jesus-sepultado-y-maria-santisima-de-soledad",
    "sepultado": "hermandad-ci-jesus-sepultado-y-maria-santisima-de-soledad",
    "hermandad-de-la-consagrada-y-venerada-imagen-de-la-santisima-virgen-de-soledad":
        "hermandad-ci-jesus-sepultado-y-maria-santisima-de-soledad",
    "desamparo": "hermandad-de-la-ci-de-santo-cristo-del-perdon-y-jesus-nazareno-del-desamparo",
    "cristo-del-perdon": "hermandad-de-la-ci-de-santo-cristo-del-perdon-y-jesus-nazareno-del-desamparo",
}


def _hermandad_editor_por_slug(slug):
    """Resuelve la organización del editor sin una lista cerrada de hermandades.

    Orden de resolución:
    1. Slug real de la base de datos (sirve para TODA organización nueva).
    2. Alias históricos para enlaces viejos.
    3. Slug generado desde el nombre, como tolerancia para enlaces manuales.

    No se exige ``activa=True`` porque el editor es una herramienta de personal
    administrativo y debe poder prepararse antes de publicar la hermandad.
    """
    slug_normalizado = slugify((slug or "").strip())
    if not slug_normalizado:
        raise Http404("Hermandad no encontrada.")

    # La ruta canónica siempre usa el slug persistido. Esto hace que las nuevas
    # hermandades funcionen sin tocar el código.
    hermandad = Hermandad.objects.filter(slug__iexact=slug_normalizado).first()
    if hermandad:
        return hermandad

    # Compatibilidad con direcciones usadas por versiones anteriores.
    slug_real = EDITOR_SLUG_ALIASES.get(slug_normalizado)
    if slug_real:
        hermandad = Hermandad.objects.filter(slug=slug_real).first()
        if hermandad:
            return hermandad

    # Tolerancia adicional: si alguien construye la URL a partir del nombre
    # visible, se intenta localizar la organización sin crear alias manuales.
    for candidata in Hermandad.objects.only("id", "nombre", "slug"):
        if slugify(candidata.nombre) == slug_normalizado:
            return candidata

    raise Http404("No existe una hermandad o cofradía asociada a esta dirección.")


def home(request):
    hermandades = Hermandad.objects.filter(activa=True).order_by("nombre")
    return render(request, "web/home.html", {"hermandades": hermandades})


def iniciar_sesion(request):
    """Selector público entre acceso de devotos y acceso administrativo."""
    return render(request, "web/iniciar_sesion.html")


def _cuenta_devoto_actual(request):
    cuenta_id = request.session.get("cuenta_devoto_id")
    if not cuenta_id:
        return None
    return CuentaDevoto.objects.filter(pk=cuenta_id, activa=True).first()


def devoto_login(request):
    if _cuenta_devoto_actual(request):
        return redirect("web:devoto_panel")

    initial = {}
    if request.method == "POST":
        form = DevotoLoginForm(request.POST)
        if form.is_valid():
            cuenta = CuentaDevoto.objects.filter(correo__iexact=form.cleaned_data["correo"]).first()
            if not cuenta or not cuenta.activa or not cuenta.check_password(form.cleaned_data["password"]):
                form.add_error(None, "Correo o contraseña incorrectos.")
            else:
                request.session.cycle_key()
                request.session["cuenta_devoto_id"] = cuenta.pk
                cuenta.ultimo_acceso = timezone.now()
                cuenta.save(update_fields=["ultimo_acceso"])
                nombre = cuenta.inscripciones.order_by("creado_en").values_list("primer_nombre", flat=True).first()
                messages.success(request, f"¡Bienvenido{', ' + nombre if nombre else ''}! Has iniciado sesión correctamente.")
                next_url = request.POST.get("next") or request.GET.get("next")
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect("web:devoto_panel")
    else:
        if request.GET.get("correo"):
            initial["correo"] = request.GET["correo"]
        form = DevotoLoginForm(initial=initial)

    return render(
        request,
        "web/devoto_login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


def devoto_panel(request):
    cuenta = _cuenta_devoto_actual(request)
    if not cuenta:
        return redirect(f"{reverse('web:devoto_login')}?next={request.path}")
    inscripciones = list(
        cuenta.inscripciones.select_related("hermandad").order_by("hermandad__nombre", "-creado_en")
    )
    nombre = inscripciones[0].nombre_completo if inscripciones else cuenta.correo
    return render(
        request,
        "web/devoto_panel.html",
        {"cuenta": cuenta, "inscripciones": inscripciones, "nombre_devoto": nombre},
    )


@require_POST
def devoto_preferencias_comunicacion(request, devoto_id):
    cuenta = _cuenta_devoto_actual(request)
    if not cuenta:
        return redirect(f"{reverse('web:devoto_login')}?next={reverse('web:devoto_panel')}")

    devoto = get_object_or_404(Devoto, pk=devoto_id, cuenta=cuenta)
    devoto.acepta_email = request.POST.get("acepta_email") == "on"
    devoto.acepta_sms = request.POST.get("acepta_sms") == "on"
    devoto.acepta_whatsapp = request.POST.get("acepta_whatsapp") == "on"
    devoto.acepta_comunicaciones = any(
        [devoto.acepta_email, devoto.acepta_sms, devoto.acepta_whatsapp]
    )
    devoto.save(
        update_fields=[
            "acepta_email",
            "acepta_sms",
            "acepta_whatsapp",
            "acepta_comunicaciones",
            "actualizado_en",
        ]
    )
    messages.success(
        request,
        f"Preferencias de comunicación actualizadas para {devoto.hermandad.nombre}.",
    )
    return redirect("web:devoto_panel")


@require_POST
def devoto_logout(request):
    request.session.pop("cuenta_devoto_id", None)
    request.session.cycle_key()
    messages.success(request, "Sesión de devoto cerrada correctamente.")
    return redirect("web:home")


def administrativo_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin:index")

    form = AdministrativoLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identificador = form.cleaned_data["usuario"].strip()
        user_model = get_user_model()
        user_obj = user_model.objects.filter(username__iexact=identificador).first()
        if user_obj is None:
            user_obj = user_model.objects.filter(email__iexact=identificador).first()

        user = authenticate(
            request,
            username=user_obj.username if user_obj else identificador,
            password=form.cleaned_data["password"],
        )
        if user and user.is_active and user.is_staff:
            login(request, user)
            messages.success(request, "Bienvenido al panel administrativo de TRADICIÓN VIVA.")
            return redirect("admin:index")
        form.add_error(None, "Credenciales incorrectas o usuario sin permisos administrativos.")

    return render(request, "web/administrativo_login.html", {"form": form})


def devoto_password_reset(request):
    form = RecuperarCuentaDevotoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        correo = form.cleaned_data["correo"]
        cuenta = CuentaDevoto.objects.filter(correo__iexact=correo).first()
        if not cuenta:
            registros_anteriores = Devoto.objects.filter(correo__iexact=correo)
            if registros_anteriores.exists():
                cuenta = CuentaDevoto(correo=correo)
                cuenta.set_password(None)
                cuenta.save()
                registros_anteriores.filter(cuenta__isnull=True).update(cuenta=cuenta)
        if cuenta and cuenta.activa:
            token = signing.dumps(
                {"id": cuenta.pk, "pwd": cuenta.password[:24]},
                salt="tradicion-viva-devoto-reset",
                compress=True,
            )
            reset_url = request.build_absolute_uri(
                reverse("web:devoto_password_reset_confirm", kwargs={"token": token})
            )
            try:
                send_mail(
                    "Restablecer contraseña - TRADICIÓN VIVA",
                    (
                        "Recibimos una solicitud para restablecer tu contraseña de devoto.\n\n"
                        f"Abre este enlace durante la próxima hora:\n{reset_url}\n\n"
                        "Si no solicitaste el cambio, ignora este mensaje."
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [cuenta.correo],
                    fail_silently=False,
                )
            except Exception:
                logger.exception("No fue posible enviar recuperación de contraseña a %s", cuenta.correo)
        messages.success(
            request,
            "Si el correo tiene una cuenta activa, recibirás un enlace para restablecer la contraseña.",
        )
        return redirect("web:devoto_login")
    return render(request, "web/devoto_password_reset.html", {"form": form})


def devoto_password_reset_confirm(request, token):
    cuenta = None
    token_valido = False
    try:
        data = signing.loads(token, salt="tradicion-viva-devoto-reset", max_age=3600)
        cuenta = CuentaDevoto.objects.filter(pk=data.get("id"), activa=True).first()
        token_valido = bool(cuenta and data.get("pwd") == cuenta.password[:24])
    except signing.BadSignature:
        token_valido = False

    form = RestablecerPasswordDevotoForm(request.POST or None) if token_valido else None
    if token_valido and request.method == "POST" and form.is_valid():
        cuenta.set_password(form.cleaned_data["password1"])
        cuenta.save(update_fields=["password"])
        messages.success(request, "Contraseña actualizada. Ya puedes iniciar sesión.")
        return redirect("web:devoto_login")

    return render(
        request,
        "web/devoto_password_reset_confirm.html",
        {"form": form, "token_valido": token_valido},
    )


def hermandad_detalle(request, slug):
    h = get_object_or_404(Hermandad, slug=slug, activa=True)
    return render(request, "web/hermandad_detalle.html", {"h": h})


def seccion_generica(request, slug, seccion):
    h = get_object_or_404(Hermandad, slug=slug, activa=True)
    titulo_seccion = SECCION_TITULOS.get(seccion, seccion.replace("-", " ").title())
    if seccion == "marchas":
        titulo_seccion = h.etiqueta_musica

    contexto = {
        "h": h,
        "seccion": seccion,
        "nombre_corto": h.nombre,
        "titulo_seccion": titulo_seccion,
    }

    if seccion == "agenda":
        # Se materializa una sola vez el queryset para reutilizarlo tanto en el
        # calendario interactivo como en el calendario HTML de respaldo. De esta
        # forma la agenda sigue siendo visible aunque JavaScript esté desactivado
        # o el navegador bloquee temporalmente el script.
        eventos = list(
            EventoAgenda.objects.select_related("hermandad")
            .filter(hermandad=h, activo=True)
            .order_by("inicio")
        )
        contexto["eventos_agenda"] = [
            {
                "id": evento.id,
                "title": evento.titulo,
                "start": evento.inicio.isoformat(),
                "end": evento.fin.isoformat() if evento.fin else "",
                "allDay": evento.todo_el_dia,
                "description": evento.descripcion,
                "location": evento.lugar,
            }
            for evento in eventos
        ]

        hoy = timezone.localdate()
        meses_es = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        eventos_por_fecha = {}
        for evento in eventos:
            inicio_local = timezone.localtime(evento.inicio) if timezone.is_aware(evento.inicio) else evento.inicio
            eventos_por_fecha.setdefault(inicio_local.date(), []).append(
                {
                    "titulo": evento.titulo,
                    "hora": "" if evento.todo_el_dia else inicio_local.strftime("%H:%M"),
                }
            )

        semanas = []
        for semana in calendar.Calendar(firstweekday=0).monthdatescalendar(hoy.year, hoy.month):
            semanas.append(
                [
                    {
                        "numero": dia.day,
                        "fecha": dia.isoformat(),
                        "mes_actual": dia.month == hoy.month,
                        "es_hoy": dia == hoy,
                        "eventos": eventos_por_fecha.get(dia, []),
                    }
                    for dia in semana
                ]
            )
        contexto["agenda_mes_titulo"] = f"{meses_es[hoy.month - 1].capitalize()} {hoy.year}"
        contexto["agenda_semanas"] = semanas
    elif seccion == "nuestras-imagenes":
        contexto["imagenes"] = h.imagenes.filter(categoria="titular", activo=True).order_by("orden", "titulo")
    elif seccion == "galeria-fotos":
        contexto["imagenes"] = h.imagenes.filter(categoria="galeria", activo=True).order_by("orden", "titulo")
    elif seccion == "galeria-filmica":
        contexto["videos"] = h.videos.filter(activo=True).order_by("orden", "titulo")
    elif seccion == "marchas":
        contexto["marchas"] = h.marchas.filter(activo=True).order_by("orden", "titulo")
    elif seccion == "registro-actualizacion-datos":
        if request.method == "POST":
            form = DevotoForm(request.POST, hermandad=h)
            if form.is_valid():
                with transaction.atomic():
                    devoto = form.save()
                messages.success(
                    request,
                    "Registro completado. Ya puedes iniciar sesión como devoto con tu correo y contraseña.",
                )
                return redirect(
                    "web:comprobante_devoto",
                    slug=h.slug,
                    codigo=devoto.comprobante_codigo,
                )
        else:
            form = DevotoForm(hermandad=h)
        contexto["form"] = form

    return render(request, "web/seccion.html", contexto)


def comprobante_devoto(request, slug, codigo):
    devoto = get_object_or_404(
        Devoto.objects.select_related("hermandad"),
        hermandad__slug=slug,
        comprobante_codigo=codigo,
    )
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="comprobante_devoto_{devoto.id}_{devoto.hermandad.slug}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    qr_url = request.build_absolute_uri(
        reverse(
            "web:comprobante_devoto",
            kwargs={"slug": devoto.hermandad.slug, "codigo": devoto.comprobante_codigo},
        )
    )
    generar_comprobante_devoto(response, devoto, qr_url)
    return response


def _turnos_context(h):
    turnos = (
        TurnoRecorrido.objects.select_related("hermandad")
        .filter(hermandad=h, activa=True)
        .order_by("orden_ruta", "numero")
    )
    turnos_data = []
    ruta_coords = []
    for turno in turnos:
        turnos_data.append(
            {
                "id": turno.id,
                "numero": turno.numero,
                "titulo": f"Turno {turno.numero} · {turno.nombre_turno}",
                "nombre_turno": turno.nombre_turno,
                "pieza": turno.pieza,
                "genero": turno.genero,
                "compositor": turno.compositor,
                "direccion": turno.direccion,
                "coords": [turno.latitud, turno.longitud],
                "latitud": turno.latitud,
                "longitud": turno.longitud,
                "orden_ruta": turno.orden_ruta,
            }
        )
        ruta_coords.append([turno.latitud, turno.longitud])
    return turnos, turnos_data, ruta_coords


def seguimiento(request, slug):
    h = get_object_or_404(Hermandad, slug=slug, activa=True)
    _, turnos_data, ruta_coords = _turnos_context(h)
    return render(
        request,
        "web/seguimiento.html",
        {
            "h": h,
            "turnos_data": turnos_data,
            "ruta_coords": ruta_coords,
        },
    )


@staff_member_required(login_url="web:administrativo_login")
def editor_turnos(request, slug):
    h = _hermandad_editor_por_slug(slug)

    if request.method == "POST":
        turno_id = request.POST.get("turno_id")
        try:
            numero = int(request.POST.get("numero", ""))
            orden_ruta = int(request.POST.get("orden_ruta", ""))
            latitud = float(request.POST.get("latitud", ""))
            longitud = float(request.POST.get("longitud", ""))
        except (TypeError, ValueError):
            messages.error(request, "Revisa el número, el orden y la ubicación del turno.")
            return redirect("web:editor_turnos", slug=h.slug)

        if turno_id:
            turno = get_object_or_404(TurnoRecorrido, id=turno_id, hermandad=h)
        else:
            turno = TurnoRecorrido(hermandad=h)

        turno.numero = numero
        turno.nombre_turno = request.POST.get("nombre_turno", "").strip()
        turno.pieza = request.POST.get("pieza", "").strip()
        turno.genero = request.POST.get("genero", "").strip()
        turno.compositor = request.POST.get("compositor", "").strip()
        turno.direccion = request.POST.get("direccion", "").strip()
        turno.latitud = latitud
        turno.longitud = longitud
        turno.orden_ruta = orden_ruta
        turno.activa = True

        if not turno.nombre_turno or not turno.pieza:
            messages.error(request, "El nombre del turno y la pieza musical son obligatorios.")
            return redirect("web:editor_turnos", slug=h.slug)

        turno.full_clean()
        turno.save()
        messages.success(request, "Turno guardado correctamente.")
        return redirect("web:editor_turnos", slug=h.slug)

    turnos, turnos_data, _ = _turnos_context(h)
    return render(
        request,
        "web/editor_turnos.html",
        {
            "h": h,
            "turnos_data": turnos_data,
            "turnos": turnos,
        },
    )


@staff_member_required(login_url="web:administrativo_login")
@require_POST
def eliminar_turno(request, slug, turno_id):
    h = _hermandad_editor_por_slug(slug)
    turno = get_object_or_404(TurnoRecorrido, id=turno_id, hermandad=h)
    turno.delete()
    messages.success(request, "Turno eliminado.")
    return redirect("web:editor_turnos", slug=h.slug)


def api_ubicacion(request, slug):
    """Devuelve la última posición asociada al identificador visible en Traccar Client.

    ``Hermandad.traccar_device_id`` guarda el ``uniqueId`` externo (por ejemplo
    81709810), no el ``id`` interno que usa la API de Traccar. Primero resolvemos
    el dispositivo de la cuenta y luego localizamos su última posición.
    """
    h = get_object_or_404(Hermandad, slug=slug, activa=True)
    if not h.gps_activo:
        return JsonResponse({"ok": False, "message": "El seguimiento GPS no está habilitado para esta organización."})

    identificador = str(h.traccar_device_id or "").strip()
    if not identificador:
        return JsonResponse({"ok": False, "message": "Identificador GPS no configurado para esta organización."})

    if not settings.TRACCAR_USERNAME or not settings.TRACCAR_PASSWORD:
        return JsonResponse(
            {
                "ok": False,
                "message": (
                    "Credenciales GPS no configuradas. Agrega TRACCAR_USERNAME y "
                    "TRACCAR_PASSWORD en el archivo .env con la misma cuenta usada en Traccar."
                ),
            }
        )

    base_url = settings.TRACCAR_BASE_URL.rstrip("/")
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    try:
        login_response = session.post(
            f"{base_url}/api/session",
            data={"email": settings.TRACCAR_USERNAME, "password": settings.TRACCAR_PASSWORD},
            timeout=10,
        )
        if login_response.status_code in (401, 403):
            return JsonResponse(
                {"ok": False, "message": "Traccar rechazó el usuario o la contraseña configurados en .env."},
                status=502,
            )
        login_response.raise_for_status()

        # El número que muestra Traccar Client es uniqueId. La API de posiciones
        # trabaja con el ID interno del dispositivo, por eso primero lo resolvemos.
        devices_response = session.get(f"{base_url}/api/devices", timeout=10)
        devices_response.raise_for_status()
        devices = devices_response.json()
        device = next(
            (d for d in devices if str(d.get("uniqueId", "")).strip() == identificador),
            None,
        )

        if not device:
            return JsonResponse(
                {
                    "ok": False,
                    "message": (
                        f"Traccar no encuentra el identificador {identificador}. "
                        "Registra ese mismo identificador como dispositivo dentro de la misma cuenta de Traccar."
                    ),
                }
            )

        internal_device_id = device.get("id")
        if internal_device_id is None:
            return JsonResponse({"ok": False, "message": "Traccar devolvió un dispositivo sin ID interno."}, status=502)

        # Sin parámetros Traccar devuelve las últimas posiciones visibles para
        # la cuenta. Filtramos por el ID interno para evitar confundirlo con uniqueId.
        positions_response = session.get(f"{base_url}/api/positions", timeout=10)
        positions_response.raise_for_status()
        positions = positions_response.json()
        matching = [p for p in positions if p.get("deviceId") == internal_device_id]

        if not matching:
            return JsonResponse(
                {
                    "ok": False,
                    "message": (
                        f"El dispositivo {identificador} está registrado, pero todavía no tiene una posición disponible. "
                        "En Traccar Client pulsa 'Enviar ubicación' y revisa 'Mostrar estado'."
                    ),
                }
            )

        position = max(
            matching,
            key=lambda p: p.get("serverTime") or p.get("deviceTime") or "",
        )
        latitude = position.get("latitude")
        longitude = position.get("longitude")
        if latitude is None or longitude is None:
            return JsonResponse({"ok": False, "message": "La última posición de Traccar no contiene coordenadas válidas."}, status=502)

        return JsonResponse(
            {
                "ok": True,
                "latitude": latitude,
                "longitude": longitude,
                "speed": position.get("speed"),
                "course": position.get("course"),
                "deviceTime": position.get("deviceTime"),
                "serverTime": position.get("serverTime"),
                "deviceName": device.get("name") or h.nombre_dispositivo_gps or "Dispositivo GPS",
                "identifier": identificador,
            }
        )
    except requests.RequestException:
        logger.exception("No fue posible consultar Traccar para %s", slug)
        return JsonResponse(
            {
                "ok": False,
                "message": (
                    "No fue posible conectar con Traccar. Verifica TRACCAR_BASE_URL, Internet y que "
                    "la cuenta pertenezca al mismo servidor configurado en Traccar Client."
                ),
            },
            status=502,
        )
    except (TypeError, ValueError, KeyError):
        logger.exception("Respuesta GPS inválida para %s", slug)
        return JsonResponse(
            {"ok": False, "message": "La respuesta del servicio GPS no es válida."},
            status=502,
        )


def robots_txt(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    return HttpResponse(f"User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: {sitemap_url}\n", content_type="text/plain")


# Compatibilidad con las direcciones anteriores de San José.
def seguimiento_san_jose(request):
    return seguimiento(request, "san-jose")


def editor_turnos_san_jose(request):
    return editor_turnos(request, "san-jose")


@require_POST
def eliminar_turno_san_jose(request, turno_id):
    return eliminar_turno(request, "san-jose", turno_id)


def api_ubicacion_san_jose(request):
    return api_ubicacion(request, "san-jose")
