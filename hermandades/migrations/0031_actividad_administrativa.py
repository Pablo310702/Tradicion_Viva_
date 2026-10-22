from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hermandades", "0030_desactivar_sms_devotos"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActividadAdministrativa",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("tipo", models.CharField(choices=[("actividad", "Actividad administrativa"), ("cambio_importante", "Cambio importante")], default="actividad", max_length=24)),
                ("accion", models.CharField(max_length=80)),
                ("modelo", models.CharField(blank=True, max_length=120)),
                ("objeto_id", models.CharField(blank=True, max_length=80)),
                ("descripcion", models.TextField()),
                ("detalles", models.JSONField(blank=True, default=dict)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("hermandad", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="actividades_administrativas", to="hermandades.hermandad")),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="actividades_administrativas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "actividad administrativa",
                "verbose_name_plural": "actividades administrativas",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="actividadadministrativa",
            index=models.Index(fields=["tipo", "creado_en"], name="actividad_tipo_fecha_idx"),
        ),
        migrations.AddIndex(
            model_name="actividadadministrativa",
            index=models.Index(fields=["hermandad", "creado_en"], name="actividad_org_fecha_idx"),
        ),
    ]
