import calendar
from datetime import timedelta, timezone as datetime_timezone
import hashlib
import json
import logging
import math
import re
from io import BytesIO

import requests
from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_user_model, login
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from hermandades.models import (
    AdministradorOrganizacion,
    CuentaDevoto,
    Devoto,
    EventoAgenda,
    Hermandad,
    InscripcionTurno,
    TurnoRecorrido,
)
from hermandades.messaging import (
    normalizar_telefono_e164,
    send_registration_receipt_email,
    send_whatsapp_document_template,
)

from .forms import (
    AdministrativoLoginForm,
    DevotoForm,
    DevotoLoginForm,
    RecuperarCuentaDevotoForm,
    RestablecerPasswordDevotoForm,
)
from .pdf_utils import generar_comprobante_devoto

logger = logging.getLogger(__name__)

MAX_ROUTE_POINTS = 2500
GPS_TURN_DEFAULT_RADIUS_METERS = 30
GPS_TURN_MIN_RADIUS_METERS = 25
GPS_TURN_MAX_RADIUS_METERS = 60
GPS_TURN_MAX_ACCURACY_METERS = 100


def _parse_route_points(raw_value):
    try:
        points = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("El trazado enviado no tiene un formato válido.") from error

    if not isinstance(points, list):
        raise ValueError("El trazado debe ser una lista de puntos.")
    if points and not 2 <= len(points) <= MAX_ROUTE_POINTS:
        raise ValueError(
            f"Cada trazado debe tener entre 2 y {MAX_ROUTE_POINTS} puntos, o estar vacío."
        )

    normalized_points = []
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Cada punto debe incluir latitud y longitud.")
        latitude, longitude = point
        if (
            isinstance(latitude, bool)
            or isinstance(longitude, bool)
            or not isinstance(latitude, (int, float))
            or not isinstance(longitude, (int, float))
            or not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError("El trazado contiene coordenadas fuera de rango.")
        normalized_points.append([float(latitude), float(longitude)])

    return normalized_points


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


def _validar_acceso_organizacion_staff(request, hermandad):
    """Impide que un administrador navegue por URL a otra organización."""
    if request.user.is_superuser:
        return

    autorizado = AdministradorOrganizacion.objects.filter(
        usuario=request.user,
        hermandad=hermandad,
        activo=True,
    ).exists()

    if not autorizado:
        raise PermissionDenied(
            "No tienes permiso para administrar esta hermandad o cofradía."
        )


def _color_organizacion(value, default):
    value = (value or "").strip()
    if re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value):
        return value
    return default


def _texto_contraste(color):
    hexadecimal = color.lstrip("#")
    if len(hexadecimal) == 3:
        hexadecimal = "".join(character * 2 for character in hexadecimal)
    rojo, verde, azul = (
        int(hexadecimal[index:index + 2], 16) / 255
        for index in (0, 2, 4)
    )
    luminancia = 0.2126 * rojo + 0.7152 * verde + 0.0722 * azul
    return "#111111" if luminancia > 0.55 else "#ffffff"


def _comprobante_qr_url(request, devoto):
    destino_qr = reverse(
        "web:qr_devoto",
        kwargs={"codigo": devoto.comprobante_codigo},
    )
    return request.build_absolute_uri(destino_qr)


def _comprobante_pdf_bytes(request, devoto):
    buffer = BytesIO()
    generar_comprobante_devoto(buffer, devoto, _comprobante_qr_url(request, devoto))
    return buffer.getvalue()


def _enviar_comprobante_registro(request, devoto):
    if not (devoto.acepta_email or devoto.acepta_whatsapp):
        return

    pdf_bytes = _comprobante_pdf_bytes(request, devoto)
    filename = f"comprobante_devoto_{devoto.id}_{devoto.hermandad.slug}.pdf"
    if devoto.acepta_email:
        try:
            send_registration_receipt_email(
                devoto.correo,
                devoto.hermandad.nombre,
                pdf_bytes,
                filename,
            )
        except Exception:
            logger.exception("No fue posible enviar por correo el comprobante del devoto %s", devoto.pk)

    if devoto.acepta_whatsapp:
        try:
            telefono = normalizar_telefono_e164(devoto.celular)
            send_whatsapp_document_template(telefono, pdf_bytes, filename)
        except Exception:
            logger.exception("No fue posible enviar por WhatsApp el comprobante del devoto %s", devoto.pk)


def home(request):
    hermandades = Hermandad.objects.filter(activa=True).order_by("nombre")
    return render(request, "web/home.html", {"hermandades": hermandades})


def iniciar_sesion(request):
    """Selector público entre acceso de devotos y acceso administrativo."""
    if _cuenta_devoto_actual(request):
        return redirect("web:devoto_panel")
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin:index")
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
                request.session.set_expiry(60 * 60 * 24 * 30 if form.cleaned_data["recordar"] else 0)
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
        {
            "form": form,
            "next": request.GET.get("next", ""),
        },
    )


def devoto_panel(request):
    cuenta = _cuenta_devoto_actual(request)
    if not cuenta:
        return redirect(f"{reverse('web:devoto_login')}?next={request.path}")
    inscripciones = list(
        cuenta.inscripciones.select_related("hermandad")
        .prefetch_related("turnos_inscritos__turno")
        .order_by("hermandad__nombre", "-creado_en")
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
    # SMS ya no es un canal disponible para los registros de devotos.
    devoto.acepta_sms = False
    devoto.acepta_whatsapp = request.POST.get("acepta_whatsapp") == "on"
    devoto.acepta_comunicaciones = any(
        [devoto.acepta_email, devoto.acepta_whatsapp]
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
            tiene_acceso = user.is_superuser or AdministradorOrganizacion.objects.filter(
                usuario=user,
                activo=True,
            ).exists()

            if tiene_acceso:
                login(request, user)
                messages.success(request, "Bienvenido al panel administrativo de TRADICIÓN VIVA.")
                return redirect("admin:index")

            form.add_error(
                None,
                "Tu usuario administrativo todavía no tiene una hermandad o cofradía asignada.",
            )
        else:
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
                request.session.cycle_key()
                request.session["cuenta_devoto_id"] = devoto.cuenta_id
                _enviar_comprobante_registro(request, devoto)
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


def qr_devoto(request, codigo):
    """
    Punto público del código QR del comprobante.

    El QR utiliza comprobante_codigo (UUID) y no expone el DPI en la URL.
    El personal autorizado puede abrir las inscripciones y confirmar entregas.
    Los demás visitantes solo llegan a la página pública de la organización.
    """
    devoto = get_object_or_404(
        Devoto.objects.select_related("hermandad"),
        comprobante_codigo=codigo,
    )

    if request.user.is_authenticated and request.user.is_staff:
        _validar_acceso_organizacion_staff(request, devoto.hermandad)
        return redirect(
            f"{reverse('web:inscripciones_turnos', kwargs={'slug': devoto.hermandad.slug})}"
            f"?codigo={devoto.comprobante_codigo}"
        )

    return redirect(
        "web:hermandad_detalle",
        slug=devoto.hermandad.slug,
    )


def comprobante_devoto(request, slug, codigo):
    cuenta = _cuenta_devoto_actual(request)
    if not cuenta:
        raise Http404

    devoto = get_object_or_404(
        Devoto.objects.select_related("hermandad"),
        hermandad__slug=slug,
        comprobante_codigo=codigo,
        cuenta=cuenta,
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="comprobante_devoto_{devoto.id}_{devoto.hermandad.slug}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"

    generar_comprobante_devoto(response, devoto, _comprobante_qr_url(request, devoto))

    return response


def _turnos_context(h):
    turnos = (
        TurnoRecorrido.objects.select_related("hermandad")
        .filter(hermandad=h, activa=True)
        .order_by("numero", "orden_ruta")
    )
    turnos_data = []
    ruta_coords = []
    for turno in turnos:
        nombre_turno = turno.nombre_turno.strip()
        nombre_repite_numero = nombre_turno.casefold() in {
            str(turno.numero),
            f"turno {turno.numero}".casefold(),
        }
        turnos_data.append(
            {
                "id": turno.id,
                "numero": turno.numero,
                "titulo": (
                    f"Turno {turno.numero}"
                    if nombre_repite_numero
                    else f"Turno {turno.numero} · {nombre_turno}"
                ),
                "nombre_turno": nombre_turno,
                "pieza": turno.pieza,
                "genero": turno.genero,
                "compositor": turno.compositor,
                "direccion": turno.direccion,
                "coords": [turno.latitud, turno.longitud],
                "latitud": turno.latitud,
                "longitud": turno.longitud,
                "orden_ruta": turno.orden_ruta,
                "alcanzado_en": turno.alcanzado_en.isoformat() if turno.alcanzado_en else None,
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
            "ruta_trazado": (h.ruta_trazado or ruta_coords) if turnos_data else [],
            "turno_cambio_direccion": h.turno_cambio_direccion,
            "gps_publicable": h.gps_publicable,
        },
    )


@staff_member_required(login_url="web:administrativo_login")
def inscripciones_turnos(request, slug):
    hermandad = _hermandad_editor_por_slug(slug)
    _validar_acceso_organizacion_staff(request, hermandad)

    if request.method == "POST":
        devoto_id = request.POST.get("devoto_id")
        devoto = get_object_or_404(Devoto, pk=devoto_id, hermandad=hermandad)
        turno_ids = list(dict.fromkeys(request.POST.getlist("turno_ids")))
        turnos = list(
            TurnoRecorrido.objects.filter(
                hermandad=hermandad,
                activa=True,
                pk__in=turno_ids,
            )
        )
        if not turno_ids or len(turnos) != len(turno_ids):
            messages.error(request, "Selecciona al menos un turno activo de esta organización.")
            return redirect(
                "web:inscripciones_turnos",
                slug=hermandad.slug,
            )

        creadas = 0
        existentes = 0
        with transaction.atomic():
            for turno in turnos:
                _, creada = InscripcionTurno.objects.get_or_create(
                    devoto=devoto,
                    turno=turno,
                    defaults={"inscrito_por": request.user},
                )
                creadas += int(creada)
                existentes += int(not creada)

        if creadas:
            messages.success(
                request,
                f"Se registraron {creadas} turno(s) para {devoto.nombre_completo}.",
            )
        if existentes:
            messages.info(
                request,
                f"{existentes} turno(s) ya estaban registrados para este devoto.",
            )
        return redirect(
            f"{reverse('web:inscripciones_turnos', kwargs={'slug': hermandad.slug})}"
            f"?codigo={devoto.comprobante_codigo}"
        )

    codigo = request.GET.get("codigo", "").strip()
    devoto_objetivo = None
    if codigo:
        devoto_objetivo = get_object_or_404(
            Devoto,
            hermandad=hermandad,
            comprobante_codigo=codigo,
        )

    inscripciones = InscripcionTurno.objects.filter(
        turno__hermandad=hermandad,
        devoto__hermandad=hermandad,
    ).select_related("devoto", "turno", "entregado_por", "inscrito_por")

    consulta = request.GET.get("q", "").strip()
    if consulta:
        inscripciones = inscripciones.filter(
            Q(devoto__primer_nombre__icontains=consulta)
            | Q(devoto__otros_nombres__icontains=consulta)
            | Q(devoto__primer_apellido__icontains=consulta)
            | Q(devoto__otros_apellidos__icontains=consulta)
            | Q(devoto__correo__icontains=consulta)
        )
    if devoto_objetivo:
        inscripciones = inscripciones.filter(devoto=devoto_objetivo)

    turnos_disponibles = TurnoRecorrido.objects.filter(
        hermandad=hermandad,
        activa=True,
    )
    devotos = Devoto.objects.filter(hermandad=hermandad).order_by(
        "primer_apellido",
        "primer_nombre",
    )
    if consulta:
        devotos = devotos.filter(
            Q(primer_nombre__icontains=consulta)
            | Q(otros_nombres__icontains=consulta)
            | Q(primer_apellido__icontains=consulta)
            | Q(otros_apellidos__icontains=consulta)
            | Q(correo__icontains=consulta)
            | Q(celular__icontains=consulta)
        )
    return render(
        request,
        "web/inscripciones_turnos.html",
        {
            "h": hermandad,
            "color_primario": _color_organizacion(
                hermandad.color_primario,
                "#111111",
            ),
            "color_acento": _color_organizacion(
                hermandad.color_acento,
                "#b08d57",
            ),
            "texto_color_primario": _texto_contraste(
                _color_organizacion(hermandad.color_primario, "#111111")
            ),
            "texto_color_acento": _texto_contraste(
                _color_organizacion(hermandad.color_acento, "#b08d57")
            ),
            "devotos": devotos,
            "devotos_encontrados": devotos.count() if consulta else None,
            "turnos_disponibles": turnos_disponibles,
            "inscripciones": inscripciones,
            "devoto_objetivo": devoto_objetivo,
            "consulta": consulta,
        },
    )


@staff_member_required(login_url="web:administrativo_login")
@require_POST
def entregar_turno(request, slug, inscripcion_id):
    hermandad = _hermandad_editor_por_slug(slug)
    _validar_acceso_organizacion_staff(request, hermandad)

    with transaction.atomic():
        inscripcion = get_object_or_404(
            InscripcionTurno.objects.select_for_update().select_related("devoto", "turno"),
            pk=inscripcion_id,
            devoto__hermandad=hermandad,
            turno__hermandad=hermandad,
        )
        ya_entregado = inscripcion.entregado
        if not ya_entregado:
            inscripcion.entregado = True
            inscripcion.entregado_en = timezone.now()
            inscripcion.entregado_por = request.user
            inscripcion.save(
                update_fields=[
                    "entregado",
                    "entregado_en",
                    "entregado_por",
                ]
            )

    if ya_entregado:
        messages.info(request, "Este turno ya estaba marcado como entregado.")
    else:
        devoto = inscripcion.devoto
        messages.success(
            request,
            f"Turno {inscripcion.turno.numero} marcado como entregado a {devoto.nombre_completo}.",
        )
        if devoto.acepta_email:
            try:
                send_mail(
                    subject=f"Turno {inscripcion.turno.numero} entregado - TRADICIÓN VIVA",
                    message=(
                        f"Hola {devoto.primer_nombre},\n\n"
                        f"Confirmamos la entrega del Turno {inscripcion.turno.numero} "
                        f"({inscripcion.turno.nombre_turno}) de {hermandad.nombre}.\n\n"
                        "Gracias por tu participación."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[devoto.correo],
                    fail_silently=False,
                )
            except Exception:
                logger.exception(
                    "Turno %s entregado, pero no se pudo notificar por correo al devoto %s",
                    inscripcion.turno_id,
                    devoto.pk,
                )
                messages.warning(
                    request,
                    "La entrega quedó registrada, pero no se pudo enviar el correo de confirmación.",
                )
        else:
            messages.info(
                request,
                "La entrega quedó registrada. El devoto no autorizó notificaciones por correo.",
            )

    return redirect(
        f"{reverse('web:inscripciones_turnos', kwargs={'slug': hermandad.slug})}"
        f"?codigo={inscripcion.devoto.comprobante_codigo}"
    )


@staff_member_required(login_url="web:administrativo_login")
@require_POST
def limpiar_entrega_turno(request, slug, inscripcion_id):
    hermandad = _hermandad_editor_por_slug(slug)
    _validar_acceso_organizacion_staff(request, hermandad)

    with transaction.atomic():
        inscripcion = get_object_or_404(
            InscripcionTurno.objects.select_for_update().select_related("devoto", "turno"),
            pk=inscripcion_id,
            devoto__hermandad=hermandad,
            turno__hermandad=hermandad,
        )
        ya_pendiente = not inscripcion.entregado
        codigo_devoto = inscripcion.devoto.comprobante_codigo
        numero_turno = inscripcion.turno.numero
        nombre_devoto = inscripcion.devoto.nombre_completo
        if not ya_pendiente:
            inscripcion.delete()

    if ya_pendiente:
        messages.info(request, "Solo se pueden quitar de la lista los turnos ya entregados.")
    else:
        messages.success(
            request,
            f"Se quitó de la lista el Turno {numero_turno} de {nombre_devoto}.",
        )

    return redirect(
        f"{reverse('web:inscripciones_turnos', kwargs={'slug': hermandad.slug})}"
        f"?codigo={codigo_devoto}"
    )


@staff_member_required(login_url="web:administrativo_login")
def editor_turnos(request, slug):
    h = _hermandad_editor_por_slug(slug)
    _validar_acceso_organizacion_staff(request, h)

    if request.method == "POST":
        if request.POST.get("action") == "reiniciar_seguimiento":
            TurnoRecorrido.objects.filter(
                hermandad=h,
                alcanzado_en__isnull=False,
            ).update(alcanzado_en=None)
            h.gps_ultimo_turno_en_zona_id = None
            h.save(update_fields=["gps_ultimo_turno_en_zona_id"])
            messages.success(request, "El progreso GPS de los turnos se reinició.")
            return redirect("web:editor_turnos", slug=h.slug)

        if request.POST.get("action") == "guardar_trazado":
            try:
                ruta_trazado = _parse_route_points(request.POST.get("ruta_trazado"))
            except ValueError as error:
                messages.error(request, str(error))
                return redirect("web:editor_turnos", slug=h.slug)

            raw_turno_cambio = request.POST.get("turno_cambio_direccion", "").strip()
            if raw_turno_cambio:
                try:
                    turno_cambio = int(raw_turno_cambio)
                except ValueError:
                    messages.error(request, "Selecciona un número de turno válido para el cambio de dirección.")
                    return redirect("web:editor_turnos", slug=h.slug)
                if turno_cambio < 0 or not TurnoRecorrido.objects.filter(
                    hermandad=h,
                    activa=True,
                    numero=turno_cambio,
                ).exists():
                    messages.error(request, "El turno seleccionado para el cambio de dirección ya no está disponible.")
                    return redirect("web:editor_turnos", slug=h.slug)
            else:
                turno_cambio = None

            h.ruta_trazado = ruta_trazado
            h.turno_cambio_direccion = turno_cambio
            h.save(update_fields=["ruta_trazado", "turno_cambio_direccion"])
            messages.success(request, "Trazado y cambio de colores del recorrido guardados correctamente.")
            return redirect("web:editor_turnos", slug=h.slug)

        turno_id = request.POST.get("turno_id")
        try:
            numero = int(request.POST.get("numero", ""))
            orden_ruta = int(request.POST.get("orden_ruta", ""))
            latitud = float(request.POST.get("latitud", ""))
            longitud = float(request.POST.get("longitud", ""))
        except (TypeError, ValueError):
            messages.error(request, "Revisa el número, el orden y la ubicación del turno.")
            return redirect("web:editor_turnos", slug=h.slug)

        if numero < 0 or orden_ruta < 0:
            messages.error(request, "El número y el orden del turno deben ser cero o mayores.")
            return redirect("web:editor_turnos", slug=h.slug)

        if turno_id:
            turno = get_object_or_404(TurnoRecorrido, id=turno_id, hermandad=h)
            latitud_anterior = turno.latitud
            longitud_anterior = turno.longitud
        else:
            turno = TurnoRecorrido(hermandad=h)
            latitud_anterior = None
            longitud_anterior = None

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
        if latitud_anterior is not None and h.ruta_trazado:
            ruta_actualizada = []
            ruta_modificada = False
            for punto in h.ruta_trazado:
                if (
                    abs(float(punto[0]) - float(latitud_anterior)) < 0.000001
                    and abs(float(punto[1]) - float(longitud_anterior)) < 0.000001
                ):
                    ruta_actualizada.append([latitud, longitud])
                    ruta_modificada = True
                else:
                    ruta_actualizada.append(punto)
            if ruta_modificada:
                h.ruta_trazado = ruta_actualizada
                h.save(update_fields=["ruta_trazado"])
        messages.success(request, "Turno guardado correctamente.")
        return redirect("web:editor_turnos", slug=h.slug)

    turnos, turnos_data, ruta_coords = _turnos_context(h)
    return render(
        request,
        "web/editor_turnos.html",
        {
            "h": h,
            "turnos_data": turnos_data,
            "turnos": turnos,
            "turnos_alcanzados": sum(turno.alcanzado_en is not None for turno in turnos),
            "ruta_trazado": h.ruta_trazado or ruta_coords,
            "turno_cambio_direccion": h.turno_cambio_direccion,
        },
    )


@staff_member_required(login_url="web:administrativo_login")
@require_POST
def eliminar_turno(request, slug, turno_id):
    h = _hermandad_editor_por_slug(slug)
    _validar_acceso_organizacion_staff(request, h)
    turno = get_object_or_404(TurnoRecorrido, id=turno_id, hermandad=h)
    with transaction.atomic():
        turno.delete()
        quedan_turnos_activos = TurnoRecorrido.objects.filter(
            hermandad=h,
            activa=True,
        ).exists()
        if not quedan_turnos_activos:
            h.ruta_trazado = []
        quedan_puntos_de_cambio = TurnoRecorrido.objects.filter(
            hermandad=h,
            activa=True,
            numero=h.turno_cambio_direccion,
        ).exists() if h.turno_cambio_direccion is not None else True
        update_fields = []
        if not quedan_turnos_activos:
            h.turno_cambio_direccion = None
            update_fields.extend(["ruta_trazado", "turno_cambio_direccion"])
        elif not quedan_puntos_de_cambio:
            h.turno_cambio_direccion = None
            update_fields.append("turno_cambio_direccion")
        if update_fields:
            h.save(update_fields=update_fields)
        if h.gps_ultimo_turno_en_zona_id == turno.pk:
            h.gps_ultimo_turno_en_zona_id = None
            h.save(update_fields=["gps_ultimo_turno_en_zona_id"])

    if quedan_turnos_activos:
        messages.success(request, "Turno eliminado.")
    else:
        messages.success(request, "Turno eliminado y trazado del recorrido limpiado.")
    return redirect("web:editor_turnos", slug=h.slug)


def _distancia_haversine_metros(latitud_a, longitud_a, latitud_b, longitud_b):
    radio_tierra = 6_371_000
    lat_a = math.radians(latitud_a)
    lat_b = math.radians(latitud_b)
    delta_lat = math.radians(latitud_b - latitud_a)
    delta_lng = math.radians(longitud_b - longitud_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lng / 2) ** 2
    )
    return radio_tierra * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _radio_llegada_turno(precision):
    if precision is None:
        return GPS_TURN_DEFAULT_RADIUS_METERS
    try:
        precision = float(precision)
    except (TypeError, ValueError):
        return GPS_TURN_DEFAULT_RADIUS_METERS
    if not math.isfinite(precision) or precision <= 0:
        return GPS_TURN_DEFAULT_RADIUS_METERS
    if precision > GPS_TURN_MAX_ACCURACY_METERS:
        return None
    return min(
        GPS_TURN_MAX_RADIUS_METERS,
        max(GPS_TURN_MIN_RADIUS_METERS, precision),
    )


def _actualizar_progreso_turnos_gps(hermandad, latitud, longitud, position_time, precision):
    radio_llegada = _radio_llegada_turno(precision)
    with transaction.atomic():
        hermandad_bloqueada = Hermandad.objects.select_for_update().get(pk=hermandad.pk)
        if (
            hermandad_bloqueada.ultima_posicion_turno_procesada_en
            and position_time < hermandad_bloqueada.ultima_posicion_turno_procesada_en
        ):
            nueva_llegada = None
        else:
            nueva_llegada = None
            turno_en_zona = None
            if hermandad_bloqueada.gps_ultimo_turno_en_zona_id is not None:
                turno_en_zona = TurnoRecorrido.objects.filter(
                    pk=hermandad_bloqueada.gps_ultimo_turno_en_zona_id,
                    hermandad=hermandad_bloqueada,
                    activa=True,
                    alcanzado_en__isnull=False,
                ).first()
                if turno_en_zona is None:
                    hermandad_bloqueada.gps_ultimo_turno_en_zona_id = None

            sigue_en_zona_anterior = bool(
                turno_en_zona
                and radio_llegada is not None
                and _distancia_haversine_metros(
                    latitud,
                    longitud,
                    turno_en_zona.latitud,
                    turno_en_zona.longitud,
                ) <= radio_llegada
            )

            if not sigue_en_zona_anterior and radio_llegada is not None:
                hermandad_bloqueada.gps_ultimo_turno_en_zona_id = None
                siguiente_turno = (
                    TurnoRecorrido.objects.select_for_update()
                    .filter(hermandad=hermandad_bloqueada, activa=True, alcanzado_en__isnull=True)
                    .order_by("numero", "orden_ruta", "pk")
                    .first()
                )
                if siguiente_turno:
                    distancia = _distancia_haversine_metros(
                        latitud,
                        longitud,
                        siguiente_turno.latitud,
                        siguiente_turno.longitud,
                    )
                    if distancia <= radio_llegada:
                        siguiente_turno.alcanzado_en = position_time
                        siguiente_turno.save(update_fields=["alcanzado_en"])
                        hermandad_bloqueada.gps_ultimo_turno_en_zona_id = siguiente_turno.pk
                        nueva_llegada = siguiente_turno

            hermandad_bloqueada.ultima_posicion_turno_procesada_en = position_time
            hermandad_bloqueada.save(
                update_fields=[
                    "ultima_posicion_turno_procesada_en",
                    "gps_ultimo_turno_en_zona_id",
                ]
            )

        turnos_alcanzados = list(
            TurnoRecorrido.objects.filter(
                hermandad=hermandad_bloqueada,
                activa=True,
                alcanzado_en__isnull=False,
            ).order_by("numero", "orden_ruta", "pk")
        )
        turno_detectado = nueva_llegada
        if turno_detectado is None and radio_llegada is not None:
            turnos_cercanos = [
                turno
                for turno in turnos_alcanzados
                if _distancia_haversine_metros(
                    latitud,
                    longitud,
                    turno.latitud,
                    turno.longitud,
                ) <= radio_llegada
            ]
            if turnos_cercanos:
                turno_detectado = min(
                    turnos_cercanos,
                    key=lambda turno: _distancia_haversine_metros(
                        latitud,
                        longitud,
                        turno.latitud,
                        turno.longitud,
                    ),
                )

        total_turnos = TurnoRecorrido.objects.filter(
            hermandad=hermandad_bloqueada,
            activa=True,
        ).count()
        return {
            "turnos_alcanzados_ids": [turno.pk for turno in turnos_alcanzados],
            "turno_detectado_id": turno_detectado.pk if turno_detectado else None,
            "turnos_alcanzados": len(turnos_alcanzados),
            "total_turnos": total_turnos,
        }


def api_ubicacion(request, slug):
    """Devuelve la última posición asociada al identificador visible en Traccar Client.

    ``Hermandad.traccar_device_id`` guarda el ``uniqueId`` externo (por ejemplo
    81709810), no el ``id`` interno que usa la API de Traccar. Primero resolvemos
    el dispositivo de la cuenta y luego localizamos su última posición.
    """
    h = get_object_or_404(Hermandad, slug=slug, activa=True)
    client_ip = request.META.get("REMOTE_ADDR", "unknown")
    ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:24]
    cache_key = f"gps-rate:{h.pk}:{ip_hash}"
    try:
        if cache.add(cache_key, 1, timeout=60):
            request_count = 1
        else:
            try:
                request_count = cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, timeout=60)
                request_count = 1
    except Exception:
        logger.exception("No fue posible consultar el limitador de GPS")
        return JsonResponse({"ok": False, "message": "El seguimiento no está disponible temporalmente."}, status=503)

    if request_count > settings.GPS_API_RATE_LIMIT_PER_MINUTE:
        response = JsonResponse(
            {"ok": False, "message": "Se alcanzó el límite de consultas GPS. Intenta de nuevo en un minuto."},
            status=429,
        )
        response["Retry-After"] = "60"
        return response

    if not h.gps_activo:
        return JsonResponse({"ok": False, "message": "El seguimiento GPS no está habilitado para esta organización."})
    if not h.gps_publicable:
        return JsonResponse(
            {"ok": False, "message": "El seguimiento GPS está fuera del horario público del evento."},
            status=403,
        )

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
        updated_at = position.get("serverTime") or position.get("deviceTime")
        position_time = parse_datetime(updated_at) if isinstance(updated_at, str) else None
        if position_time is None:
            return JsonResponse({"ok": False, "message": "Traccar no devolvió la hora de la ubicación."}, status=502)
        if timezone.is_naive(position_time):
            position_time = timezone.make_aware(position_time, datetime_timezone.utc)
        age = timezone.now() - position_time
        if age < timedelta(minutes=-1) or age > timedelta(minutes=settings.GPS_MAX_POSITION_AGE_MINUTES):
            return JsonResponse({"ok": False, "message": "La última ubicación GPS está desactualizada."})

        latitude = position.get("latitude")
        longitude = position.get("longitude")
        if latitude is None or longitude is None:
            return JsonResponse({"ok": False, "message": "La última posición de Traccar no contiene coordenadas válidas."}, status=502)
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "message": "Traccar devolvió coordenadas GPS no válidas."}, status=502)
        if (
            not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            return JsonResponse({"ok": False, "message": "Traccar devolvió coordenadas GPS fuera de rango."}, status=502)

        progreso_turnos = _actualizar_progreso_turnos_gps(
            h,
            latitude,
            longitude,
            position_time,
            position.get("accuracy"),
        )

        return JsonResponse(
            {
                "ok": True,
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": position.get("accuracy"),
                "updatedAt": position_time.isoformat(),
                **progreso_turnos,
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
