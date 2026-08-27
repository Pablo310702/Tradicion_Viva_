import django.db.models.deletion
from django.db import migrations, models


def migrar_consentimiento_correo(apps, schema_editor):
    """El consentimiento histórico solo mencionaba correo; se conserva como email."""
    Devoto = apps.get_model("hermandades", "Devoto")
    Devoto.objects.filter(acepta_comunicaciones=True).update(acepta_email=True)


class Migration(migrations.Migration):

    dependencies = [
        ("hermandades", "0010_accesos_tipo_comunicados"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devoto",
            name="acepta_comunicaciones",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Indicador general de que el devoto autorizó al menos un canal de comunicación. "
                    "Se mantiene por compatibilidad con registros anteriores."
                ),
                verbose_name="autoriza comunicaciones",
            ),
        ),
        migrations.AddField(
            model_name="devoto",
            name="acepta_email",
            field=models.BooleanField(
                default=False,
                help_text="Permite enviar avisos, saludos e información institucional por correo electrónico.",
                verbose_name="autoriza correo electrónico",
            ),
        ),
        migrations.AddField(
            model_name="devoto",
            name="acepta_sms",
            field=models.BooleanField(
                default=False,
                help_text="Permite enviar avisos, saludos e información institucional por mensaje SMS.",
                verbose_name="autoriza SMS",
            ),
        ),
        migrations.AddField(
            model_name="devoto",
            name="acepta_whatsapp",
            field=models.BooleanField(
                default=False,
                help_text="Permite enviar avisos, saludos e información institucional por WhatsApp.",
                verbose_name="autoriza WhatsApp",
            ),
        ),
        migrations.RunPython(migrar_consentimiento_correo, migrations.RunPython.noop),
        migrations.AddField(
            model_name="comunicado",
            name="enviar_email",
            field=models.BooleanField(default=True, verbose_name="enviar por correo"),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="enviar_sms",
            field=models.BooleanField(default=False, verbose_name="enviar por SMS"),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="enviar_whatsapp",
            field=models.BooleanField(default=False, verbose_name="enviar por WhatsApp"),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="whatsapp_modo",
            field=models.CharField(
                choices=[
                    ("template", "Plantilla aprobada por Meta (recomendado)"),
                    ("text", "Texto libre (solo dentro de la ventana permitida por WhatsApp)"),
                ],
                default="template",
                max_length=12,
                verbose_name="modo de envío por WhatsApp",
            ),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="whatsapp_template_name",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Opcional. Si queda vacío se usa WHATSAPP_DEFAULT_TEMPLATE_NAME del archivo .env. "
                    "La plantilla recomendada contiene dos variables de cuerpo: {{1}} nombre y {{2}} mensaje."
                ),
                max_length=120,
                verbose_name="nombre de plantilla de WhatsApp",
            ),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="whatsapp_template_language",
            field=models.CharField(
                default="es",
                help_text="Código de idioma aprobado en Meta, por ejemplo es, es_MX o en_US.",
                max_length=12,
                verbose_name="idioma de plantilla",
            ),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="whatsapp_template_param_mode",
            field=models.CharField(
                choices=[
                    ("name_message", "2 variables: nombre + mensaje"),
                    ("message", "1 variable: mensaje"),
                    ("none", "Sin variables (por ejemplo, hello_world)"),
                ],
                default="name_message",
                help_text=(
                    "Selecciona cuántas variables de cuerpo espera la plantilla aprobada. "
                    "Para la plantilla sugerida usa nombre + mensaje."
                ),
                max_length=16,
                verbose_name="variables de la plantilla",
            ),
        ),
        migrations.AlterField(
            model_name="comunicado",
            name="mensaje",
            field=models.TextField(
                help_text=(
                    "Puedes personalizar el contenido con {nombre}, {primer_nombre}, {organizacion}, "
                    "{tipo_organizacion} y {asunto}."
                )
            ),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="total_email_enviados",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="total_email_fallidos",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="total_sms_enviados",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="total_sms_fallidos",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="total_whatsapp_enviados",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="comunicado",
            name="total_whatsapp_fallidos",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.CreateModel(
            name="EnvioComunicado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "canal",
                    models.CharField(
                        choices=[
                            ("email", "Correo electrónico"),
                            ("sms", "SMS"),
                            ("whatsapp", "WhatsApp"),
                        ],
                        max_length=12,
                    ),
                ),
                ("destinatario", models.CharField(max_length=254)),
                ("proveedor", models.CharField(blank=True, max_length=40)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("aceptado", "Aceptado por el proveedor"),
                            ("entregado", "Entregado"),
                            ("fallido", "Fallido"),
                            ("omitido", "Omitido"),
                        ],
                        default="aceptado",
                        max_length=12,
                    ),
                ),
                ("proveedor_message_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("proveedor_estado", models.CharField(blank=True, max_length=80)),
                ("detalle_error", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "comunicado",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="envios",
                        to="hermandades.comunicado",
                    ),
                ),
                (
                    "devoto",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="envios_comunicados",
                        to="hermandades.devoto",
                    ),
                ),
            ],
            options={
                "verbose_name": "envío de comunicado",
                "verbose_name_plural": "envíos de comunicados",
                "ordering": ["-creado_en"],
                "indexes": [
                    models.Index(fields=["comunicado", "canal", "estado"], name="envio_com_canal_estado")
                ],
            },
        ),
    ]
