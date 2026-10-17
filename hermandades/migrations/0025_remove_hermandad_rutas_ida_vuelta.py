from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("hermandades", "0024_hermandad_ruta_trazado"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="hermandad",
            name="ruta_ida",
        ),
        migrations.RemoveField(
            model_name="hermandad",
            name="ruta_vuelta",
        ),
    ]
