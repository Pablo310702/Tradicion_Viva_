from hermandades.models import ActividadAdministrativa


def request_ip(request):
    """Return the safest client IP available for the current request."""
    if not request:
        return None
    return request.META.get("REMOTE_ADDR")


def registrar_actividad(
    request,
    accion,
    descripcion,
    *,
    tipo=ActividadAdministrativa.ACTIVIDAD,
    hermandad=None,
    objeto=None,
    detalles=None,
):
    """Persist an administrative action without interrupting the user flow."""
    usuario = getattr(request, "user", None) if request else None
    if not getattr(usuario, "is_authenticated", False):
        usuario = None
    modelo = objeto.__class__.__name__ if objeto is not None else ""
    objeto_id = str(getattr(objeto, "pk", "") or "")
    return ActividadAdministrativa.objects.create(
        usuario=usuario,
        hermandad=hermandad,
        tipo=tipo,
        accion=accion,
        modelo=modelo,
        objeto_id=objeto_id,
        descripcion=descripcion,
        detalles=detalles or {},
        ip=request_ip(request),
    )
