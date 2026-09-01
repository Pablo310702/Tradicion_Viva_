from django.core.exceptions import ValidationError


def validate_file_size(file, max_mb: int, label: str) -> None:
    if file and file.size > max_mb * 1024 * 1024:
        raise ValidationError(
            f"{label} no puede superar {max_mb} MB."
        )


def validate_image_size(file) -> None:
    validate_file_size(file, 100, "La imagen")


def validate_audio_size(file) -> None:
    validate_file_size(file, 20, "El audio") 

def validate_video_size(file) -> None:
    validate_file_size(file, 1024, "El video")