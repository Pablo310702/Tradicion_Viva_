from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0006_devoto_comprobante_medicion"),
    ]

    operations = [
        migrations.AddField(
            model_name="hermandad",
            name="gps_activo",
            field=models.BooleanField(
                default=False,
                help_text="Activa el seguimiento en vivo para esta hermandad o cofradía.",
                verbose_name="seguimiento GPS activo",
            ),
        ),
        migrations.AddField(
            model_name="hermandad",
            name="nombre_dispositivo_gps",
            field=models.CharField(
                blank=True,
                help_text="Nombre descriptivo opcional, por ejemplo: Teléfono procesión o Teltonika principal.",
                max_length=120,
                verbose_name="nombre del dispositivo GPS",
            ),
        ),
        migrations.AddField(
            model_name="hermandad",
            name="traccar_device_id",
            field=models.PositiveBigIntegerField(
                blank=True,
                help_text="ID numérico del dispositivo registrado en Traccar.",
                null=True,
                unique=True,
                verbose_name="ID de dispositivo Traccar",
            ),
        ),
    ]
