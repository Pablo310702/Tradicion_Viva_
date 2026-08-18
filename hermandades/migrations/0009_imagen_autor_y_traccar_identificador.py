from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hermandades", "0008_permitir_device_id_traccar_compartido"),
    ]

    operations = [
        migrations.AddField(
            model_name="imagenhermandad",
            name="autor",
            field=models.CharField(
                blank=True,
                help_text="Crédito visible de la imagen, por ejemplo: Fotografía: Juan Pérez o Archivo Histórico.",
                max_length=180,
                verbose_name="autor / fotografía",
            ),
        ),
        migrations.AlterField(
            model_name="hermandad",
            name="traccar_device_id",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Identificador que muestra Traccar Client (por ejemplo, 81709810). "
                    "No es el ID interno de la base de datos de Traccar y puede compartirse entre varias organizaciones."
                ),
                max_length=80,
                null=True,
                verbose_name="identificador del dispositivo Traccar",
            ),
        ),
    ]
