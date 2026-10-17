from collections import Counter

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_file_size(file, max_mb: int, label: str) -> None:
    if file and file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"{label} no puede superar {max_mb} MB.")


def validate_image_size(file) -> None:
    validate_file_size(file, settings.MAX_IMAGE_UPLOAD_MB, "La imagen")


def validate_audio_size(file) -> None:
    validate_file_size(file, 20, "El audio")


def validate_video_size(file) -> None:
    validate_file_size(file, settings.MAX_VIDEO_UPLOAD_MB, "El video")


def validate_organization_media_quota(organization, incoming_bytes: int, replaced_names=()) -> None:
    """Reject uploads that exceed an organization's total stored-media quota."""
    if not organization or not organization.pk:
        return

    records = [(organization, ("imagen_templo", "logo", "portada"))]
    for relation_name, field_names in (
        ("imagenes", ("imagen", "miniatura")),
        ("videos", ("video",)),
        ("marchas", ("audio",)),
    ):
        records.extend(
            (record, field_names)
            for record in getattr(organization, relation_name).all()
        )

    replaced = Counter(name for name in replaced_names if name)
    used_bytes = 0
    for record, field_names in records:
        for field_name in field_names:
            stored_file = getattr(record, field_name, None)
            if not stored_file or not stored_file.name:
                continue
            if replaced[stored_file.name]:
                replaced[stored_file.name] -= 1
                continue
            try:
                used_bytes += stored_file.size
            except FileNotFoundError:
                # El registro puede conservar una referencia a un archivo
                # eliminado manualmente del almacenamiento.
                continue
            except OSError as exc:
                raise ValidationError(
                    "No fue posible comprobar el espacio utilizado por la organización. "
                    "Verifica la conexión o los permisos del almacenamiento de archivos."
                ) from exc

    quota_bytes = organization.almacenamiento_cuota_mb * 1024 * 1024
    if used_bytes + incoming_bytes > quota_bytes:
        raise ValidationError(
            f"La organización superaría su cuota de {organization.almacenamiento_cuota_mb} MB de archivos."
        )
