from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from hermandades.models import Devoto, EventoAgenda, Hermandad, ImagenHermandad, TurnoRecorrido


class BaseProjectTestCase(TestCase):
    def setUp(self):
        self.hermandad = Hermandad.objects.create(
            nombre="Cofradía de prueba",
            templo="Templo de prueba",
            ciudad="Antigua Guatemala",
            slug="cofradia-prueba",
            activa=True,
        )


class PublicViewsTests(BaseProjectTestCase):
    def test_home_lists_active_organizations(self):
        response = self.client.get(reverse("web:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.hermandad.nombre)

    def test_nombre_corto_is_in_section_context(self):
        response = self.client.get(
            reverse(
                "web:seccion_generica",
                kwargs={"slug": self.hermandad.slug, "seccion": "mision-vision"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["nombre_corto"], self.hermandad.nombre)

    def test_agenda_renders_interactive_and_html_fallback_calendar(self):
        response = self.client.get(
            reverse(
                "web:seccion_generica",
                kwargs={"slug": self.hermandad.slug, "seccion": "agenda"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="agendaApp"')
        self.assertContains(response, 'id="agendaCalendar"')
        self.assertContains(response, "data-calendar-fallback")
        self.assertContains(response, "Mes")
        self.assertContains(response, "Semana")
        self.assertContains(response, "Día")

    def test_gps_api_reports_disabled_when_organization_has_no_gps(self):
        response = self.client.get(
            reverse("web:api_ubicacion", kwargs={"slug": self.hermandad.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertIn("no está habilitado", response.json()["message"])

    def test_gps_configuration_is_stored_per_organization(self):
        self.hermandad.gps_activo = True
        self.hermandad.traccar_device_id = "98765"
        self.hermandad.nombre_dispositivo_gps = "Teltonika procesión"
        self.hermandad.full_clean()
        self.hermandad.save()

        configured = Hermandad.objects.get(pk=self.hermandad.pk)
        self.assertTrue(configured.gps_configurado)
        self.assertEqual(configured.traccar_device_id, "98765")
        self.assertEqual(configured.nombre_dispositivo_gps, "Teltonika procesión")

    def test_traccar_device_id_puede_compartirse(self):
        """Varias hermandades pueden apuntar al mismo dispositivo de Traccar."""
        from hermandades.models import Hermandad

        self.hermandad.traccar_device_id = "81709810"
        self.hermandad.save()
        otra = Hermandad.objects.create(
            nombre="Hermandad GPS compartido",
            slug="hermandad-gps-compartido",
            traccar_device_id="81709810",
        )
        self.assertEqual(otra.traccar_device_id, self.hermandad.traccar_device_id)

    def test_imagen_admite_credito_de_autor(self):
        field = ImagenHermandad._meta.get_field("autor")
        self.assertEqual(field.max_length, 180)
        self.assertTrue(field.blank)

    @override_settings(
        TRACCAR_BASE_URL="https://traccar.example",
        TRACCAR_USERNAME="usuario@example.com",
        TRACCAR_PASSWORD="secreto",
    )
    def test_gps_resuelve_unique_id_antes_de_buscar_posicion(self):
        from unittest.mock import Mock, patch

        self.hermandad.gps_activo = True
        self.hermandad.traccar_device_id = "81709810"
        self.hermandad.save()

        login = Mock(status_code=200)
        login.raise_for_status.return_value = None
        devices = Mock(status_code=200)
        devices.raise_for_status.return_value = None
        devices.json.return_value = [{"id": 42, "uniqueId": "81709810", "name": "Teléfono Procesión"}]
        positions = Mock(status_code=200)
        positions.raise_for_status.return_value = None
        positions.json.return_value = [{
            "deviceId": 42,
            "latitude": 14.5566,
            "longitude": -90.7332,
            "deviceTime": "2026-08-18T18:00:00Z",
        }]

        fake_session = Mock()
        fake_session.post.return_value = login
        fake_session.get.side_effect = [devices, positions]

        with patch("web.views.requests.Session", return_value=fake_session):
            response = self.client.get(reverse("web:api_ubicacion", kwargs={"slug": self.hermandad.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["identifier"], "81709810")
        self.assertEqual(response.json()["deviceName"], "Teléfono Procesión")

    def test_section_menu_keeps_live_tracking_link(self):
        response = self.client.get(
            reverse(
                "web:seccion_generica",
                kwargs={"slug": self.hermandad.slug, "seccion": "agenda"},
            )
        )
        self.assertContains(response, "Recorrido")
        self.assertContains(response, "Seguimiento en vivo")
        self.assertContains(
            response, reverse("web:seguimiento", kwargs={"slug": self.hermandad.slug})
        )

    def test_agenda_only_exposes_active_events(self):
        now = timezone.now()
        EventoAgenda.objects.create(
            hermandad=self.hermandad,
            titulo="Evento visible",
            inicio=now + timedelta(days=1),
            activo=True,
        )
        EventoAgenda.objects.create(
            hermandad=self.hermandad,
            titulo="Evento oculto",
            inicio=now + timedelta(days=2),
            activo=False,
        )
        response = self.client.get(
            reverse(
                "web:seccion_generica",
                kwargs={"slug": self.hermandad.slug, "seccion": "agenda"},
            )
        )
        titles = [event["title"] for event in response.context["eventos_agenda"]]
        self.assertEqual(titles, ["Evento visible"])

    def test_registration_saves_devoto(self):
        payload = {
            "dpi": "1234567890101",
            "primer_nombre": "Ana",
            "otros_nombres": "María",
            "primer_apellido": "López",
            "otros_apellidos": "Pérez",
            "dia": "5",
            "mes": "8",
            "anio": "1995",
            "departamento": "Sacatepéquez",
            "municipio": "Antigua Guatemala",
            "celular": "5555-5555",
            "correo": "ana@example.com",
            "correo2": "ana@example.com",
            "medida_hombro_cm": "148.0",
            "acepta_privacidad": "on",
            "website": "",
        }
        response = self.client.post(
            reverse(
                "web:seccion_generica",
                kwargs={
                    "slug": self.hermandad.slug,
                    "seccion": "registro-actualizacion-datos",
                },
            ),
            payload,
        )
        self.assertEqual(response.status_code, 302)
        pdf_response = self.client.get(response.url)
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", pdf_response["Content-Disposition"])
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))
        devoto = Devoto.objects.get(hermandad=self.hermandad)
        self.assertEqual(devoto.dpi, payload["dpi"])
        self.assertEqual(float(devoto.medida_hombro_cm), 148.0)

    def test_registration_form_has_no_gender_and_uses_centimeters(self):
        response = self.client.get(
            reverse(
                "web:seccion_generica",
                kwargs={"slug": self.hermandad.slug, "seccion": "registro-actualizacion-datos"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="genero"')
        self.assertContains(response, 'id="id_medida_hombro_cm"')
        self.assertContains(response, '1.48 m (148.0 cm)')
        self.assertContains(response, 'id="orgMenuToggle"')
        self.assertContains(response, 'id="orgMenuDrawer"')

    def test_registration_rejects_mismatched_email(self):
        payload = {
            "dpi": "1234567890101",
            "primer_nombre": "Ana",
            "primer_apellido": "López",
            "dia": "5",
            "mes": "8",
            "anio": "1995",
            "departamento": "Sacatepéquez",
            "municipio": "Antigua Guatemala",
            "celular": "5555-5555",
            "correo": "ana@example.com",
            "correo2": "otra@example.com",
            "acepta_privacidad": "on",
            "website": "",
        }
        response = self.client.post(
            reverse(
                "web:seccion_generica",
                kwargs={
                    "slug": self.hermandad.slug,
                    "seccion": "registro-actualizacion-datos",
                },
            ),
            payload,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Los correos no coinciden")
        self.assertFalse(Devoto.objects.exists())


class AdminOnlyEditorTests(BaseProjectTestCase):
    def test_editor_redirects_anonymous_user_to_admin_login(self):
        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_user_can_open_editor(self):
        user = get_user_model().objects.create_user(
            username="staff",
            password="test-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno 1",
            pieza="Marcha",
            latitud=14.55,
            longitud=-90.73,
            orden_ruta=1,
        )
        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editor de turnos")

    def test_editor_works_for_a_new_organization_without_code_changes(self):
        nueva = Hermandad.objects.create(
            nombre="Hermandad Nueva de Prueba",
            templo="Templo nuevo",
            ciudad="Antigua Guatemala",
            slug="hermandad-nueva-de-prueba",
            activa=True,
        )
        user = get_user_model().objects.create_user(
            username="staff-nueva",
            password="test-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": nueva.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, nueva.nombre)

    def test_editor_can_prepare_an_inactive_new_organization(self):
        nueva = Hermandad.objects.create(
            nombre="Hermandad en preparación",
            templo="Templo",
            ciudad="Antigua Guatemala",
            slug="hermandad-en-preparacion",
            activa=False,
        )
        user = get_user_model().objects.create_user(
            username="staff-inactiva",
            password="test-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": nueva.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, nueva.nombre)

    def test_editor_link_is_hidden_from_public_navigation_even_for_staff(self):
        user = get_user_model().objects.create_user(
            username="staff-nav",
            password="test-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("web:hermandad_detalle", kwargs={"slug": self.hermandad.slug}))
        editor_url = reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug})
        self.assertNotContains(response, editor_url)
        self.assertNotContains(response, "Editor de turnos")

    def test_old_soledad_editor_url_is_accepted(self):
        soledad = Hermandad.objects.create(
            nombre="Hermandad C.I. Jesús Sepultado y María Santísima de Soledad",
            templo="Templo",
            ciudad="Antigua Guatemala",
            slug="hermandad-ci-jesus-sepultado-y-maria-santisima-de-soledad",
            activa=True,
        )
        user = get_user_model().objects.create_user(
            username="staff-soledad",
            password="test-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        response = self.client.get(
            "/Hermandad-de-la-consagrada-y-venerada-imagen-de-la-santisima-virgen-de-soledad/editor-turnos/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, soledad.nombre)


class SeoTests(BaseProjectTestCase):
    def test_sitemap_and_robots_are_available(self):
        sitemap_response = self.client.get("/sitemap.xml")
        robots_response = self.client.get("/robots.txt")
        self.assertEqual(sitemap_response.status_code, 200)
        self.assertContains(sitemap_response, self.hermandad.get_absolute_url())
        self.assertEqual(robots_response.status_code, 200)
        self.assertContains(robots_response, "Disallow: /admin/")
