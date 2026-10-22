from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Genera un respaldo JSON de la base de datos de TRADICIÓN VIVA."

    def handle(self, *args, **options):
        backup_dir = Path(
            getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "backups")
        )
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"tradicion_viva_{timestamp}.json"
        with backup_path.open("w", encoding="utf-8", newline="") as backup_file:
            call_command(
                "dumpdata",
                "--natural-foreign",
                "--natural-primary",
                "--indent",
                "2",
                stdout=backup_file,
            )
        self.stdout.write(self.style.SUCCESS(f"Respaldo creado: {backup_path}"))
