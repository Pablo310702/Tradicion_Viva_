"""Entrega de archivos multimedia con soporte para solicitudes HTTP Range.

Los navegadores móviles suelen pedir los videos por fragmentos. El servidor
estático de desarrollo de Django no siempre incluye esa respuesta parcial,
por lo que Safari/iOS puede mostrar el reproductor sin iniciar el video.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET


_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)$")


@require_GET
def media_file(request, path: str):
    """Sirve un archivo de MEDIA_ROOT, incluyendo respuestas 206 parciales."""

    media_root = Path(settings.MEDIA_ROOT).resolve()
    requested_file = (media_root / path).resolve()

    try:
        requested_file.relative_to(media_root)
    except ValueError as exc:
        raise Http404("Archivo multimedia no encontrado") from exc

    if not requested_file.is_file():
        raise Http404("Archivo multimedia no encontrado")

    file_size = requested_file.stat().st_size
    content_type = mimetypes.guess_type(requested_file.name)[0] or "application/octet-stream"
    range_header = request.headers.get("Range", "")
    range_match = _RANGE_PATTERN.fullmatch(range_header.strip()) if range_header else None

    if not range_match:
        response = FileResponse(
            requested_file.open("rb"),
            content_type=content_type,
        )
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(file_size)
        response["Content-Disposition"] = f'inline; filename="{requested_file.name}"'
        return response

    start_text, end_text = range_match.groups()
    if not start_text and not end_text:
        return HttpResponse(status=416, headers={"Content-Range": f"bytes */{file_size}"})

    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
    else:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            return HttpResponse(status=416, headers={"Content-Range": f"bytes */{file_size}"})
        start = max(file_size - suffix_length, 0)
        end = file_size - 1

    if start >= file_size or start > end:
        return HttpResponse(status=416, headers={"Content-Range": f"bytes */{file_size}"})

    end = min(end, file_size - 1)
    length = end - start + 1
    file_handle = requested_file.open("rb")
    file_handle.seek(start)
    response = FileResponse(file_handle, status=206, content_type=content_type)
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response["Content-Disposition"] = f'inline; filename="{requested_file.name}"'
    return response
