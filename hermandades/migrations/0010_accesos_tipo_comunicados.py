import django.db.models.deletion
from django.db import migrations, models


def clasificar_organizaciones(apps, schema_editor):
    Hermandad = apps.get_model("hermandades", "Hermandad")
    Hermandad.objects.filter(nombre__istartswith="Cofradía").update(tipo_organizacion="cofradia")
    Hermandad.objects.filter(nombre__istartswith="Cofradia").update(tipo_organizacion="cofradia")


class Migration(migrations.Migration):

    dependencies = [
        ("hermandades", "0009_imagen_autor_y_traccar_identificador"),
    ]

    operations = [
        migrations.CreateModel(
            name="CuentaDevoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("correo", models.EmailField(max_length=254, unique=True)),
                ("password", models.CharField(max_length=128)),
                ("activa", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("ultimo_acceso", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "cuenta de devoto",
                "verbose_name_plural": "cuentas de devotos",
                "ordering": ["correo"],
            },
        ),
        migrations.AddField(
            model_name="hermandad",
            name="tipo_organizacion",
            field=models.CharField(
                choices=[("hermandad", "Hermandad"), ("cofradia", "Cofradía")],
                default="hermandad",
                max_length=12,
                verbose_name="tipo de organización",
            ),
        ),
        migrations.AddField(
            model_name="devoto",
            name="acepta_comunicaciones",
            field=models.BooleanField(
                default=False,
                help_text="Permite enviar avisos, saludos e información institucional al correo registrado.",
                verbose_name="autoriza comunicaciones",
            ),
        ),
        migrations.AddField(
            model_name="devoto",
            name="cuenta",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inscripciones",
                to="hermandades.cuentadevoto",
            ),
        ),
        migrations.CreateModel(
            name="Comunicado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asunto", models.CharField(max_length=180)),
                ("mensaje", models.TextField()),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("enviado_en", models.DateTimeField(blank=True, null=True)),
                ("total_enviados", models.PositiveIntegerField(default=0, editable=False)),
                ("total_fallidos", models.PositiveIntegerField(default=0, editable=False)),
                (
                    "hermandad",
                    models.ForeignKey(
                        blank=True,
                        help_text="Déjalo vacío para enviar a devotos autorizados de todas las organizaciones.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comunicados",
                        to="hermandades.hermandad",
                    ),
                ),
            ],
            options={
                "verbose_name": "comunicado masivo",
                "verbose_name_plural": "comunicados masivos",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AlterModelOptions(
            name="marchaprocesional",
            options={
                "ordering": ["orden", "titulo"],
                "verbose_name": "pieza musical",
                "verbose_name_plural": "repertorio musical",
            },
        ),
        migrations.RunPython(clasificar_organizaciones, migrations.RunPython.noop),
    ]
