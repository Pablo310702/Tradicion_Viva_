from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hermandades", "0022_inscripcionturno"),
    ]

    operations = [
        migrations.AddField(
            model_name="hermandad",
            name="ruta_ida",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="trazado de ida",
            ),
        ),
        migrations.AddField(
            model_name="hermandad",
            name="ruta_vuelta",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="trazado de vuelta",
            ),
        ),
    ]
