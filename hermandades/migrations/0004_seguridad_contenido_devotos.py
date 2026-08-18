import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import hermandades.validators


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0003_eventoagenda"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="hermandad",
            options={
                "ordering": ["nombre"],
                "verbose_name": "hermandad o cofradía",
                "verbose_name_plural": "hermandades y cofradías",
            },
        ),
        migrations.AddField(
            model_name="hermandad",
            name="informacion_templo",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="hermandad",
            name="mision",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="hermandad",
            name="vision",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="hermandad",
            name="logo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="logos/",
                validators=[
                    hermandades.validators.validate_image_size,
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["jpg", "jpeg", "png", "webp"]
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="hermandad",
            name="portada",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="portadas/",
                validators=[
                    hermandades.validators.validate_image_size,
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["jpg", "jpeg", "png", "webp"]
                    ),
                ],
            ),
        ),
        migrations.AlterUniqueTogether(
            name="turnorecorrido",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="turnorecorrido",
            constraint=models.UniqueConstraint(
                fields=("hermandad", "numero", "orden_ruta"),
                name="turno_org_numero_orden_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="eventoagenda",
            index=models.Index(
                fields=["hermandad", "activo", "inicio"],
                name="agenda_org_act_inicio",
            ),
        ),
        migrations.CreateModel(
            name="Devoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "dpi",
                    models.CharField(
                        max_length=13,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^\\d{13}$",
                                "El DPI debe contener exactamente 13 dígitos.",
                            )
                        ],
                    ),
                ),
                ("primer_nombre", models.CharField(max_length=80)),
                ("otros_nombres", models.CharField(blank=True, max_length=120)),
                ("primer_apellido", models.CharField(max_length=80)),
                ("otros_apellidos", models.CharField(blank=True, max_length=120)),
                (
                    "genero",
                    models.CharField(
                        choices=[("masculino", "Masculino"), ("femenino", "Femenino")],
                        max_length=12,
                    ),
                ),
                ("fecha_nacimiento", models.DateField()),
                ("departamento", models.CharField(max_length=100)),
                ("municipio", models.CharField(max_length=100)),
                (
                    "celular",
                    models.CharField(
                        max_length=20,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[0-9+() -]{8,20}$",
                                "Ingresa un número de celular válido.",
                            )
                        ],
                    ),
                ),
                ("correo", models.EmailField(max_length=254)),
                ("medida_hombro_px", models.PositiveIntegerField(blank=True, null=True)),
                ("acepta_privacidad", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "hermandad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="devotos",
                        to="hermandades.hermandad",
                    ),
                ),
            ],
            options={
                "verbose_name": "devoto registrado",
                "verbose_name_plural": "devotos registrados",
                "ordering": ["-creado_en"],
                "indexes": [
                    models.Index(fields=["hermandad", "creado_en"], name="devoto_org_creado"),
                    models.Index(fields=["correo"], name="devoto_correo_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("hermandad", "dpi"),
                        name="devoto_org_dpi_uniq",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ImagenHermandad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "categoria",
                    models.CharField(
                        choices=[("titular", "Nuestras imágenes"), ("galeria", "Galería de fotos")],
                        default="galeria",
                        max_length=20,
                    ),
                ),
                ("titulo", models.CharField(max_length=160)),
                ("descripcion", models.TextField(blank=True)),
                (
                    "imagen",
                    models.ImageField(
                        upload_to="galeria/",
                        validators=[
                            hermandades.validators.validate_image_size,
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=["jpg", "jpeg", "png", "webp"]
                            ),
                        ],
                    ),
                ),
                ("miniatura", models.ImageField(blank=True, editable=False, upload_to="miniaturas/")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "hermandad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="imagenes",
                        to="hermandades.hermandad",
                    ),
                ),
            ],
            options={
                "verbose_name": "imagen institucional",
                "verbose_name_plural": "imágenes institucionales",
                "ordering": ["orden", "titulo"],
                "indexes": [
                    models.Index(
                        fields=["hermandad", "categoria", "activo", "orden"],
                        name="imagen_org_cat_act",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MarchaProcesional",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=180)),
                ("compositor", models.CharField(blank=True, max_length=180)),
                ("descripcion", models.TextField(blank=True)),
                (
                    "audio",
                    models.FileField(
                        blank=True,
                        upload_to="marchas/",
                        validators=[
                            hermandades.validators.validate_audio_size,
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=["mp3", "m4a", "ogg", "wav"]
                            ),
                        ],
                    ),
                ),
                ("enlace", models.URLField(blank=True)),
                ("orden", models.PositiveIntegerField(default=0)),
                ("activo", models.BooleanField(default=True)),
                (
                    "hermandad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="marchas",
                        to="hermandades.hermandad",
                    ),
                ),
            ],
            options={
                "verbose_name": "marcha procesional",
                "verbose_name_plural": "marchas procesionales",
                "ordering": ["orden", "titulo"],
                "indexes": [
                    models.Index(
                        fields=["hermandad", "activo", "orden"],
                        name="marcha_org_act_orden",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="VideoHermandad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=180)),
                ("descripcion", models.TextField(blank=True)),
                ("url", models.URLField(help_text="Enlace de YouTube o Vimeo.")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("activo", models.BooleanField(default=True)),
                (
                    "hermandad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="videos",
                        to="hermandades.hermandad",
                    ),
                ),
            ],
            options={
                "verbose_name": "video institucional",
                "verbose_name_plural": "videos institucionales",
                "ordering": ["orden", "titulo"],
                "indexes": [
                    models.Index(
                        fields=["hermandad", "activo", "orden"],
                        name="video_org_act_orden",
                    )
                ],
            },
        ),
    ]
