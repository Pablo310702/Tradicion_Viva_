from django.shortcuts import render, get_object_or_404, redirect
from hermandades.models import Hermandad, TurnoRecorrido
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
import requests


def home(request):
    hermandades = Hermandad.objects.filter(activa=True).order_by("nombre")
    return render(request, "web/home.html", {"hermandades": hermandades})


def hermandad_detalle(request, slug):
    h = get_object_or_404(Hermandad, slug=slug, activa=True)
    return render(request, "web/hermandad_detalle.html", {"h": h})


def seccion_generica(request, slug, seccion):
    h = get_object_or_404(Hermandad, slug=slug, activa=True)
    return render(
        request,
        "web/seccion.html",
        {
            "h": h,
            "seccion": seccion,
        },
    )


def seguimiento_san_jose(request):
    h = get_object_or_404(Hermandad, slug="san-jose", activa=True)

    turnos = TurnoRecorrido.objects.filter(
        hermandad=h,
        activa=True
    ).order_by("orden_ruta", "numero")

    turnos_data = []
    ruta_coords = []

    for t in turnos:
        item = {
            "id": t.id,
            "numero": t.numero,
            "titulo": f"Turno {t.numero} · {t.nombre_turno}",
            "nombre_turno": t.nombre_turno,
            "pieza": t.pieza,
            "genero": t.genero,
            "compositor": t.compositor,
            "direccion": t.direccion,
            "coords": [t.latitud, t.longitud],
            "orden_ruta": t.orden_ruta,
        }
        turnos_data.append(item)
        ruta_coords.append([t.latitud, t.longitud])

    return render(
        request,
        "web/seguimiento_san_jose.html",
        {
            "h": h,
            "turnos_data": turnos_data,
            "ruta_coords": ruta_coords,
        },
    )


def editor_turnos_san_jose(request):
    h = get_object_or_404(Hermandad, slug="san-jose", activa=True)

    if request.method == "POST":
        turno_id = request.POST.get("turno_id")

        numero = request.POST.get("numero")
        nombre_turno = request.POST.get("nombre_turno")
        pieza = request.POST.get("pieza")
        genero = request.POST.get("genero")
        compositor = request.POST.get("compositor")
        direccion = request.POST.get("direccion")
        latitud = request.POST.get("latitud")
        longitud = request.POST.get("longitud")
        orden_ruta = request.POST.get("orden_ruta")

        if turno_id:
            turno = get_object_or_404(TurnoRecorrido, id=turno_id, hermandad=h)
        else:
            turno = TurnoRecorrido(hermandad=h)

        turno.numero = int(numero)
        turno.nombre_turno = nombre_turno
        turno.pieza = pieza
        turno.genero = genero
        turno.compositor = compositor
        turno.direccion = direccion
        turno.latitud = float(latitud)
        turno.longitud = float(longitud)
        turno.orden_ruta = int(orden_ruta)
        turno.activa = True
        turno.save()

        messages.success(request, "Turno guardado correctamente.")
        return redirect("web:editor_turnos_san_jose")

    turnos = TurnoRecorrido.objects.filter(hermandad=h, activa=True).order_by("numero", "orden_ruta")

    turnos_data = []
    for t in turnos:
        turnos_data.append({
            "id": t.id,
            "numero": t.numero,
            "nombre_turno": t.nombre_turno,
            "pieza": t.pieza,
            "genero": t.genero,
            "compositor": t.compositor,
            "direccion": t.direccion,
            "latitud": t.latitud,
            "longitud": t.longitud,
            "orden_ruta": t.orden_ruta,
        })

    return render(
        request,
        "web/editor_turnos_san_jose.html",
        {
            "h": h,
            "turnos_data": turnos_data,
            "turnos": turnos,
        },
    )


@require_POST
def eliminar_turno_san_jose(request, turno_id):
    h = get_object_or_404(Hermandad, slug="san-jose", activa=True)
    turno = get_object_or_404(TurnoRecorrido, id=turno_id, hermandad=h)
    turno.delete()
    messages.success(request, "Turno eliminado.")
    return redirect("web:editor_turnos_san_jose")


def api_ubicacion_san_jose(request):
    base_url = settings.TRACCAR_BASE_URL.rstrip("/")
    username = settings.TRACCAR_USERNAME
    password = settings.TRACCAR_PASSWORD
    device_id = settings.TRACCAR_DEVICE_ID_SAN_JOSE

    try:
        session = requests.Session()

        login_response = session.post(
            f"{base_url}/api/session",
            data={"email": username, "password": password},
            timeout=10
        )
        login_response.raise_for_status()

        positions_response = session.get(
            f"{base_url}/api/positions",
            params={"deviceId": device_id},
            timeout=10
        )
        positions_response.raise_for_status()

        data = positions_response.json()

        if not data:
            return JsonResponse({"ok": False, "message": "No hay posiciones todavía."})

        pos = data[-1]

        return JsonResponse({
            "ok": True,
            "latitude": pos.get("latitude"),
            "longitude": pos.get("longitude"),
            "speed": pos.get("speed"),
            "course": pos.get("course"),
            "deviceTime": pos.get("deviceTime"),
            "serverTime": pos.get("serverTime"),
        })

    except Exception as e:
        return JsonResponse({
            "ok": False,
            "message": str(e)
        })