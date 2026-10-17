from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hermandades", "0023_hermandad_rutas_manuales"),
    ]

    operations = [
        migrations.AddField(
            model_name="hermandad",
            name="ruta_trazado",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="trazado editable del recorrido",
            ),
        ),
    ]
