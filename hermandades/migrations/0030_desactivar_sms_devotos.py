from django.db import migrations


def desactivar_sms_devotos(apps, schema_editor):
    Devoto = apps.get_model("hermandades", "Devoto")
    Devoto.objects.all().update(acepta_sms=False)


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0029_vincular_devotos_cuentas"),
    ]

    operations = [
        migrations.RunPython(desactivar_sms_devotos, migrations.RunPython.noop),
    ]
