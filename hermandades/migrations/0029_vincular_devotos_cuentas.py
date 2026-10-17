from django.db import migrations


def vincular_devotos_cuentas(apps, schema_editor):
    CuentaDevoto = apps.get_model("hermandades", "CuentaDevoto")
    Devoto = apps.get_model("hermandades", "Devoto")

    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config(%s, %s, false), set_config(%s, %s, false)",
                ["app.current_organization_id", "*", "app.current_account_id", ""],
            )

    for cuenta in CuentaDevoto.objects.all().iterator():
        Devoto.objects.filter(
            cuenta__isnull=True,
            correo__iexact=cuenta.correo,
        ).update(cuenta_id=cuenta.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0028_gps_turno_zona"),
    ]

    operations = [
        migrations.RunPython(vincular_devotos_cuentas, migrations.RunPython.noop),
    ]
