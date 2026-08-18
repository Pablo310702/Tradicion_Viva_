import uuid

from django.db import migrations, models


def asignar_codigos_comprobante(apps, schema_editor):
    Devoto = apps.get_model("hermandades", "Devoto")
    for devoto in Devoto.objects.filter(comprobante_codigo__isnull=True).iterator():
        devoto.comprobante_codigo = uuid.uuid4()
        devoto.save(update_fields=["comprobante_codigo"])


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0005_alter_hermandad_logo_alter_hermandad_portada_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="devoto",
            name="genero",
        ),
        migrations.RemoveField(
            model_name="devoto",
            name="medida_hombro_px",
        ),
        migrations.AddField(
            model_name="devoto",
            name="medida_hombro_cm",
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="devoto",
            name="comprobante_codigo",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(asignar_codigos_comprobante, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="devoto",
            name="comprobante_codigo",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
