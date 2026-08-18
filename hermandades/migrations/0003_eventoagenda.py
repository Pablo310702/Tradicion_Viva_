from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("hermandades", "0002_alter_hermandad_options_hermandad_email_contacto_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventoAgenda",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=200)),
                ("descripcion", models.TextField(blank=True)),
                ("lugar", models.CharField(blank=True, max_length=220)),
                ("inicio", models.DateTimeField()),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("todo_el_dia", models.BooleanField(default=False)),
                ("activo", models.BooleanField(default=True)),
                ("hermandad", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="eventos_agenda", to="hermandades.hermandad")),
            ],
            options={
                "verbose_name": "evento de agenda",
                "verbose_name_plural": "eventos de agenda",
                "ordering": ["inicio", "titulo"],
            },
        ),
    ]
