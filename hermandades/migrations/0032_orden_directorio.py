from django.db import migrations, models


def ordenar_directorio(apps, schema_editor):
    Hermandad = apps.get_model("hermandades", "Hermandad")
    for hermandad in Hermandad.objects.all().order_by("nombre", "pk"):
        hermandad.orden_directorio = 0 if "san jos" in hermandad.nombre.casefold() else 1000 + hermandad.pk
        hermandad.save(update_fields=["orden_directorio"])


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0031_actividad_administrativa"),
    ]

    operations = [
        migrations.AddField(
            model_name="hermandad",
            name="orden_directorio",
            field=models.PositiveIntegerField(
                default=1000,
                help_text="Los números menores aparecen primero. Usa 0 para fijar una organización al inicio.",
                verbose_name="orden en el directorio",
            ),
        ),
        migrations.RunPython(ordenar_directorio, migrations.RunPython.noop),
    ]
