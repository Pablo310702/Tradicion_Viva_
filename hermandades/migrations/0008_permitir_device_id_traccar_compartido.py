from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0007_hermandad_gps_dinamico"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hermandad",
            name="traccar_device_id",
            field=models.PositiveBigIntegerField(
                blank=True,
                help_text=(
                    "ID numérico del dispositivo registrado en Traccar. "
                    "El mismo ID puede utilizarse en varias hermandades o cofradías."
                ),
                null=True,
                verbose_name="ID de dispositivo Traccar",
            ),
        ),
    ]
