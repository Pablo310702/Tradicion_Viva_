import json
import os
from datetime import date, timedelta
from unittest.mock import patch

from django.core import mail
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from hermandades.models import (
    AdministradorOrganizacion,
    CuentaDevoto,
    Devoto,
    EventoAgenda,
    Hermandad,
    InscripcionTurno,
    ImagenHermandad,
    TurnoRecorrido,
)


class BaseProjectTestCase(TestCase):
    def setUp(self):
        self.hermandad = Hermandad.objects.create(
            nombre="Cofradía de prueba",
            templo="Templo de prueba",
            ciudad="Antigua Guatemala",
            slug="cofradia-prueba",
            activa=True,
        )


class HealthEndpointTests(TestCase):
    def test_health_returns_liveness_payload_without_database_access(self):
        response = self.client.get(reverse("web:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_health_rejects_non_get_requests(self):
        response = self.client.post(reverse("web:health"))

        self.assertEqual(response.status_code, 405)


class AuthenticationApiTests(BaseProjectTestCase):
    def setUp(self):
        super().setUp()
        self.account = CuentaDevoto.objects.create(correo="devoto@example.com")
        self.account.set_password("ClaveSegura123")
        self.account.save()

    def test_api_login_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            reverse("web:api_auth_login"),
            data=json.dumps({"email": "devoto@example.com", "password": "ClaveSegura123"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("accessToken", response.json()["tokens"])
        self.assertIn("refreshToken", response.json()["tokens"])

    def test_api_me_accepts_access_token(self):
        login_response = self.client.post(
            reverse("web:api_auth_login"),
            data=json.dumps({"email": "devoto@example.com", "password": "ClaveSegura123"}),
            content_type="application/json",
        )
        access_token = login_response.json()["tokens"]["accessToken"]

        response = self.client.get(
            reverse("web:api_auth_me"),
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], "devoto@example.com")

    def test_refresh_rotates_token_and_rejects_replay(self):
        login = self.client.post(
            reverse("web:api_auth_login"),
            data=json.dumps({"email": "devoto@example.com", "password": "ClaveSegura123"}),
            content_type="application/json",
        )
        old_refresh = login.json()["tokens"]["refreshToken"]

        refreshed = self.client.post(
            reverse("web:api_auth_refresh"),
            data=json.dumps({"refreshToken": old_refresh}),
            content_type="application/json",
        )
        self.assertEqual(refreshed.status_code, 200)
        self.assertNotEqual(refreshed.json()["tokens"]["refreshToken"], old_refresh)

        replay = self.client.post(
            reverse("web:api_auth_refresh"),
            data=json.dumps({"refreshToken": old_refresh}),
            content_type="application/json",
        )
        self.assertEqual(replay.status_code, 401)

    def test_logout_revokes_api_session(self):
        login = self.client.post(
            reverse("web:api_auth_login"),
            data=json.dumps({"email": "devoto@example.com", "password": "ClaveSegura123"}),
            content_type="application/json",
        )
        tokens = login.json()["tokens"]

        logout = self.client.post(
            reverse("web:api_auth_logout"),
            HTTP_AUTHORIZATION=f"Bearer {tokens['accessToken']}",
        )
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("web:api_auth_me"),
                HTTP_AUTHORIZATION=f"Bearer {tokens['accessToken']}",
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                reverse("web:api_auth_refresh"),
                data=json.dumps({"refreshToken": tokens["refreshToken"]}),
                content_type="application/json",
            ).status_code,
            401,
        )


class OrganizationIsolationTests(TestCase):
    def setUp(self):
        self.organization_a = Hermandad.objects.create(
            nombre="Hermandad A",
            slug="hermandad-a",
        )
        self.organization_b = Hermandad.objects.create(
            nombre="Cofradía B",
            slug="cofradia-b",
        )
        self.user = get_user_model().objects.create_user(
            username="admin-a",
            password="ClaveAdmin123",
            is_staff=True,
            is_active=True,
        )
        AdministradorOrganizacion.objects.create(
            usuario=self.user,
            hermandad=self.organization_a,
            activo=True,
        )
        now = timezone.now()
        self.event_a = EventoAgenda.objects.create(
            hermandad=self.organization_a,
            titulo="Evento de A",
            inicio=now,
        )
        self.event_b = EventoAgenda.objects.create(
            hermandad=self.organization_b,
            titulo="Evento de B",
            inicio=now,
        )

    def test_admin_list_only_contains_assigned_organization(self):
        self.assertTrue(self.client.login(username="admin-a", password="ClaveAdmin123"))

        response = self.client.get(reverse("admin:hermandades_eventoagenda_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event_a.titulo)
        self.assertNotContains(response, self.event_b.titulo)

    def test_admin_cannot_open_other_organization_record_by_id(self):
        self.assertTrue(self.client.login(username="admin-a", password="ClaveAdmin123"))

        response = self.client.get(
            reverse(
                "admin:hermandades_eventoagenda_change",
                args=[self.event_b.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse("admin:index"),
        )

    def test_postgresql_rls_filters_rows_at_database_layer(self):
        if connection.vendor != "postgresql":
            self.skipTest("Row-level security se valida con PostgreSQL en CI.")
        role = os.environ.get("RLS_TEST_ROLE", "").strip()
        if not role:
            self.skipTest("Configura RLS_TEST_ROLE con un rol PostgreSQL sin BYPASSRLS.")

        with connection.cursor() as cursor:
            cursor.execute(
                f"GRANT SELECT ON hermandades_eventoagenda TO {connection.ops.quote_name(role)}"
            )
            cursor.execute(f"SET ROLE {connection.ops.quote_name(role)}")
            cursor.execute(
                "SELECT set_config('app.current_organization_id', %s, false)",
                [str(self.organization_a.pk)],
            )
        try:
            self.assertTrue(EventoAgenda.objects.filter(pk=self.event_a.pk).exists())
            self.assertFalse(EventoAgenda.objects.filter(pk=self.event_b.pk).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute("SELECT set_config('app.current_organization_id', '', false)")


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.organization_a = Hermandad.objects.create(
            nombre="Cofradía Rosario",
            slug="cofradia-rosario-dashboard",
            activa=True,
        )
        self.organization_b = Hermandad.objects.create(
            nombre="Hermandad Cristo",
            slug="hermandad-cristo-dashboard",
            activa=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="dashboard-general",
            email="dashboard@example.com",
            password="ClaveAdmin123",
        )

    def _create_devoto(self, hermandad, dpi, cuenta=None):
        return Devoto.objects.create(
            cuenta=cuenta,
            hermandad=hermandad,
            dpi=dpi,
            primer_nombre="Devoto",
            primer_apellido="Prueba",
            fecha_nacimiento=date(1990, 1, 1),
            departamento="Guatemala",
            municipio="Guatemala",
            celular="55555555",
            correo=f"{dpi}@example.com",
            acepta_privacidad=True,
        )

    def _create_turno(self, hermandad, numero):
        return TurnoRecorrido.objects.create(
            hermandad=hermandad,
            numero=numero,
            nombre_turno=f"Turno {numero}",
            pieza="Marcha de prueba",
            latitud=14.55,
            longitud=-90.73,
            orden_ruta=numero,
            activa=True,
        )

    def test_superuser_filters_update_metrics_and_chart_data(self):
        cuenta = CuentaDevoto.objects.create(correo="con-cuenta@example.com")
        self._create_devoto(self.organization_a, "1111111111111", cuenta=cuenta)
        self._create_devoto(self.organization_a, "2222222222222")
        self._create_devoto(self.organization_b, "3333333333333")

        turno_ocupado = self._create_turno(self.organization_a, 1)
        self._create_turno(self.organization_a, 2)
        InscripcionTurno.objects.create(
            devoto=Devoto.objects.get(dpi="1111111111111"),
            turno=turno_ocupado,
        )

        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("web:admin_dashboard"),
            {
                "organizacion": self.organization_a.pk,
                "estado": "con_cuenta",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_devotos"], 1)
        self.assertEqual(response.context["org_stats"][0]["devotos"], 1)
        self.assertEqual(sum(item["registros"] for item in response.context["registro_stats"]), 1)
        self.assertEqual(response.context["turnos_totales"], 2)
        self.assertEqual(response.context["turnos_ocupados"], 1)
        self.assertEqual(response.context["turnos_disponibles"], 1)
        self.assertEqual(response.context["ocupacion_porcentaje"], 50)

        date_filtered = self.client.get(
            reverse("web:admin_dashboard"),
            {
                "organizacion": self.organization_a.pk,
                "desde": (date.today() + timedelta(days=1)).isoformat(),
                "hasta": (date.today() + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(date_filtered.context["total_devotos"], 0)
        self.assertEqual(
            sum(item["registros"] for item in date_filtered.context["registro_stats"]),
            0,
        )

    def test_dashboard_distinguishes_gps_states(self):
        now = timezone.now()
        self.organization_a.gps_activo = True
        self.organization_a.traccar_device_id = "gps-activo"
        self.organization_a.ultima_posicion_turno_procesada_en = now
        self.organization_a.save(update_fields=[
            "gps_activo",
            "traccar_device_id",
            "ultima_posicion_turno_procesada_en",
        ])

        self.organization_b.gps_activo = True
        self.organization_b.traccar_device_id = "gps-inactivo"
        self.organization_b.ultima_posicion_turno_procesada_en = now - timedelta(minutes=10)
        self.organization_b.save(update_fields=[
            "gps_activo",
            "traccar_device_id",
            "ultima_posicion_turno_procesada_en",
        ])

        self.client.force_login(self.superuser)
        response = self.client.get(reverse("web:admin_dashboard"))

        self.assertEqual(response.context["gps_total"], 2)
        self.assertEqual(response.context["gps_activos"], 1)
        self.assertEqual(response.context["gps_inactivos"], 1)
        self.assertEqual(response.context["gps_sin_configuracion"], 0)

    def test_superuser_can_switch_organizations_and_export_filtered_values(self):
        self._create_devoto(self.organization_a, "4444444444444")
        self._create_devoto(self.organization_b, "5555555555555")
        self.client.force_login(self.superuser)

        selected = self.client.get(
            reverse("web:admin_dashboard"),
            {"organizacion": self.organization_b.pk},
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.context["total_organizaciones"], 1)
        self.assertEqual(selected.context["organizacion_visual"], self.organization_b)
        self.assertContains(selected, self.organization_b.nombre)

        exported = self.client.get(
            reverse("web:admin_dashboard"),
            {"organizacion": self.organization_b.pk, "export": "csv"},
        )
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Devotos registrados", exported.content.decode("utf-8-sig"))
        self.assertIn("1", exported.content.decode("utf-8-sig"))

    def test_superuser_has_global_organization_selector(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("web:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["organizaciones_selector"]), 2)
        self.assertTrue(response.context["puede_filtrar_organizaciones"])

    def test_organization_admin_cannot_switch_to_another_organization(self):
        admin_user = get_user_model().objects.create_user(
            username="dashboard-organizacion",
            password="ClaveAdmin123",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(
            usuario=admin_user,
            hermandad=self.organization_a,
            activo=True,
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("web:admin_dashboard"),
            {"organizacion": self.organization_b.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_organizaciones"], 1)
        self.assertEqual(response.context["organizacion_visual"], self.organization_a)
        self.assertEqual(response.context["organizacion_seleccionada"], "")
        self.assertFalse(response.context["puede_filtrar_organizaciones"])

    def test_devoto_without_administrative_session_cannot_open_dashboard(self):
        response = self.client.get(reverse("web:admin_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("iniciar-sesion/administrativo", response["Location"])


class PublicViewsTests(BaseProjectTestCase):
    def test_home_links_to_participant_directory_without_listing_organizations(self):
        response = self.client.get(reverse("web:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hermandades y Cofradías Participantes")
        self.assertNotContains(response, self.hermandad.nombre)

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

    def test_gps_publication_requires_a_valid_event_window(self):
        self.hermandad.gps_activo = True
        self.hermandad.gps_publico = True
        self.hermandad.traccar_device_id = "98765"
        with self.assertRaisesMessage(Exception, "Define el inicio y el fin"):
            self.hermandad.full_clean()

        self.hermandad.gps_publicacion_desde = timezone.now() + timedelta(hours=1)
        self.hermandad.gps_publicacion_hasta = timezone.now()
        with self.assertRaisesMessage(Exception, "El fin debe ser posterior"):
            self.hermandad.full_clean()

    @override_settings(GPS_API_RATE_LIMIT_PER_MINUTE=1)
    def test_gps_api_limits_requests_per_client(self):
        cache.clear()
        url = reverse("web:api_ubicacion", kwargs={"slug": self.hermandad.slug})
        self.assertEqual(self.client.get(url).status_code, 200)
        limited = self.client.get(url)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited["Retry-After"], "60")
        cache.clear()

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
        self.hermandad.gps_publico = True
        self.hermandad.gps_publicacion_desde = timezone.now() - timedelta(minutes=1)
        self.hermandad.gps_publicacion_hasta = timezone.now() + timedelta(hours=1)
        self.hermandad.traccar_device_id = "81709810"
        self.hermandad.save()
        turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno inicial",
            pieza="Marcha de prueba",
            latitud=14.5566,
            longitud=-90.7332,
            orden_ruta=1,
        )

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
            "deviceTime": timezone.now().isoformat(),
        }]

        fake_session = Mock()
        fake_session.post.return_value = login
        fake_session.get.side_effect = [devices, positions]

        with patch("web.views.requests.Session", return_value=fake_session):
            response = self.client.get(reverse("web:api_ubicacion", kwargs={"slug": self.hermandad.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIn("updatedAt", response.json())
        self.assertEqual(response.json()["turno_detectado_id"], turno.pk)
        self.assertEqual(response.json()["turnos_alcanzados_ids"], [turno.pk])
        self.assertNotIn("identifier", response.json())
        self.assertNotIn("deviceName", response.json())

    def test_gps_marks_next_turn_in_order_and_requires_leaving_previous_stop(self):
        from web.views import _actualizar_progreso_turnos_gps

        primer_turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno 1",
            pieza="Primera marcha",
            latitud=14.5566,
            longitud=-90.7332,
            orden_ruta=1,
        )
        segundo_turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=2,
            nombre_turno="Turno 2",
            pieza="Segunda marcha",
            latitud=14.5576,
            longitud=-90.7332,
            orden_ruta=2,
        )
        tiempo = timezone.now()

        fuera_de_orden = _actualizar_progreso_turnos_gps(
            self.hermandad,
            segundo_turno.latitud,
            segundo_turno.longitud,
            tiempo,
            None,
        )
        self.assertEqual(fuera_de_orden["turnos_alcanzados_ids"], [])

        llegada_inicial = _actualizar_progreso_turnos_gps(
            self.hermandad,
            primer_turno.latitud,
            primer_turno.longitud,
            tiempo + timedelta(seconds=30),
            None,
        )
        self.assertEqual(llegada_inicial["turnos_alcanzados_ids"], [primer_turno.pk])

        misma_parada = _actualizar_progreso_turnos_gps(
            self.hermandad,
            primer_turno.latitud,
            primer_turno.longitud,
            tiempo + timedelta(minutes=1),
            None,
        )
        self.assertEqual(misma_parada["turnos_alcanzados_ids"], [primer_turno.pk])

        _actualizar_progreso_turnos_gps(
            self.hermandad,
            14.5570,
            -90.7332,
            tiempo + timedelta(minutes=2),
            None,
        )
        llegada_siguiente = _actualizar_progreso_turnos_gps(
            self.hermandad,
            segundo_turno.latitud,
            segundo_turno.longitud,
            tiempo + timedelta(minutes=3),
            None,
        )
        self.assertEqual(
            llegada_siguiente["turnos_alcanzados_ids"],
            [primer_turno.pk, segundo_turno.pk],
        )
        self.assertEqual(llegada_siguiente["turno_detectado_id"], segundo_turno.pk)

    def test_gps_does_not_process_the_same_position_twice(self):
        from web.views import _actualizar_progreso_turnos_gps

        turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno 1",
            pieza="Marcha de prueba",
            latitud=14.5566,
            longitud=-90.7332,
            orden_ruta=1,
        )
        tiempo = timezone.now()

        primera_consulta = _actualizar_progreso_turnos_gps(
            self.hermandad,
            turno.latitud,
            turno.longitud,
            tiempo,
            None,
        )
        repetida = _actualizar_progreso_turnos_gps(
            self.hermandad,
            turno.latitud,
            turno.longitud,
            tiempo,
            None,
        )

        self.assertEqual(primera_consulta["turnos_alcanzados_ids"], [turno.pk])
        self.assertEqual(repetida["turnos_alcanzados_ids"], [turno.pk])
        turno.refresh_from_db()
        self.assertEqual(turno.alcanzado_en, tiempo)

    def test_gps_rechecks_same_position_when_turn_is_added_afterward(self):
        from web.views import _actualizar_progreso_turnos_gps

        tiempo = timezone.now()
        _actualizar_progreso_turnos_gps(
            self.hermandad,
            14.5566,
            -90.7332,
            tiempo,
            None,
        )
        turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno 1",
            pieza="Marcha inicial",
            latitud=14.5566,
            longitud=-90.7332,
            orden_ruta=1,
        )

        progreso = _actualizar_progreso_turnos_gps(
            self.hermandad,
            turno.latitud,
            turno.longitud,
            tiempo,
            None,
        )

        self.assertEqual(progreso["turno_detectado_id"], turno.pk)
        self.assertEqual(progreso["turnos_alcanzados_ids"], [turno.pk])

    def test_section_menu_keeps_live_tracking_link(self):
        ahora = timezone.now()
        self.hermandad.gps_activo = True
        self.hermandad.gps_publico = True
        self.hermandad.gps_publicacion_desde = ahora - timedelta(hours=1)
        self.hermandad.gps_publicacion_hasta = ahora + timedelta(hours=1)
        self.hermandad.traccar_device_id = "test-device"
        self.hermandad.save(
            update_fields=[
                "gps_activo",
                "gps_publico",
                "gps_publicacion_desde",
                "gps_publicacion_hasta",
                "traccar_device_id",
            ]
        )

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

    def test_tracking_hides_empty_optional_turn_fields(self):
        TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="1",
            pieza="Marcha de prueba",
            latitud=14.5566,
            longitud=-90.7332,
            orden_ruta=1,
        )

        response = self.client.get(
            reverse("web:seguimiento", kwargs={"slug": self.hermandad.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="datoGenero" hidden')
        self.assertContains(response, '${turno.genero ?')
        self.assertNotContains(response, 'Género:</strong> ${turno.genero || "--"}')
        self.assertContains(response, "const DISTANCIA_DETECCION_TURNO_METROS = 5")
        self.assertNotContains(response, "turnoMasCercano")
        self.assertEqual(response.context["turnos_data"][0]["titulo"], "Turno 1")

    def test_tracking_keeps_distinct_turn_name_with_number(self):
        for numero, nombre in ((1, "Entrada"), (2, "Turno 2")):
            TurnoRecorrido.objects.create(
                hermandad=self.hermandad,
                numero=numero,
                nombre_turno=nombre,
                pieza="Marcha de prueba",
                latitud=14.55 + numero / 1000,
                longitud=-90.7332,
                orden_ruta=numero,
            )

        response = self.client.get(
            reverse("web:seguimiento", kwargs={"slug": self.hermandad.slug})
        )

        self.assertEqual(
            [turno["titulo"] for turno in response.context["turnos_data"]],
            ["Turno 1 · Entrada", "Turno 2"],
        )

    def test_tracking_route_uses_turn_number_before_point_order(self):
        for numero, orden_ruta, latitud in (
            (10, 1, 14.10),
            (11, 2, 14.11),
            (1, 11, 14.01),
        ):
            TurnoRecorrido.objects.create(
                hermandad=self.hermandad,
                numero=numero,
                nombre_turno=f"Turno {numero}",
                pieza="Marcha de prueba",
                latitud=latitud,
                longitud=-90.7332,
                orden_ruta=orden_ruta,
            )

        response = self.client.get(
            reverse("web:seguimiento", kwargs={"slug": self.hermandad.slug})
        )

        self.assertEqual(
            [turno["numero"] for turno in response.context["turnos_data"]],
            [1, 10, 11],
        )
        self.assertEqual(
            response.context["ruta_coords"],
            [[14.01, -90.7332], [14.10, -90.7332], [14.11, -90.7332]],
        )

    def test_tracking_uses_edited_route_line_when_available(self):
        TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno inicial",
            pieza="Marcha de prueba",
            latitud=14.55,
            longitud=-90.73,
            orden_ruta=1,
        )
        trazado = [[14.55, -90.73], [14.555, -90.735], [14.56, -90.74]]
        self.hermandad.ruta_trazado = trazado
        self.hermandad.save(update_fields=["ruta_trazado"])

        response = self.client.get(
            reverse("web:seguimiento", kwargs={"slug": self.hermandad.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ruta_trazado"], trazado)
        self.assertContains(response, 'id="ruta-trazado-data"')

    def test_tracking_hides_saved_route_when_no_active_turns_remain(self):
        self.hermandad.ruta_trazado = [[14.55, -90.73], [14.56, -90.74]]
        self.hermandad.save(update_fields=["ruta_trazado"])

        response = self.client.get(
            reverse("web:seguimiento", kwargs={"slug": self.hermandad.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ruta_trazado"], [])
        self.assertContains(response, '<script id="ruta-trazado-data" type="application/json">[]</script>')

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
            "password1": "ClaveSegura123",
            "password2": "ClaveSegura123",
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

    def test_receipt_requires_the_owning_devoto_session(self):
        owner = CuentaDevoto.objects.create(correo="owner@example.com")
        devoto = Devoto.objects.create(
            cuenta=owner,
            hermandad=self.hermandad,
            dpi="1234567890101",
            primer_nombre="Ana",
            primer_apellido="Prueba",
            fecha_nacimiento=date(1995, 8, 5),
            departamento="Sacatepéquez",
            municipio="Antigua Guatemala",
            celular="55555555",
            correo=owner.correo,
            acepta_privacidad=True,
        )
        receipt_url = reverse(
            "web:comprobante_devoto",
            kwargs={"slug": self.hermandad.slug, "codigo": devoto.comprobante_codigo},
        )

        self.assertEqual(self.client.get(receipt_url).status_code, 404)

        other = CuentaDevoto.objects.create(correo="other@example.com")
        session = self.client.session
        session["cuenta_devoto_id"] = other.pk
        session.save()
        self.assertEqual(self.client.get(receipt_url).status_code, 404)

        session = self.client.session
        session["cuenta_devoto_id"] = owner.pk
        session.save()
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_emails_pdf_and_sends_whatsapp_when_authorized(self):
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
            "correo2": "ana@example.com",
            "password1": "ClaveSegura123",
            "password2": "ClaveSegura123",
            "acepta_privacidad": "on",
            "acepta_email": "on",
            "acepta_whatsapp": "on",
            "website": "",
        }
        with patch("web.views.send_whatsapp_document_template") as send_whatsapp:
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
        self.assertEqual(len(mail.outbox), 1)
        attachment = mail.outbox[0].attachments[0]
        self.assertEqual(attachment[0].split(".")[-1], "pdf")
        self.assertEqual(attachment[2], "application/pdf")
        self.assertTrue(attachment[1].startswith(b"%PDF"))
        send_whatsapp.assert_called_once()
        self.assertEqual(send_whatsapp.call_args.args[0], "+50255555555")
        self.assertTrue(send_whatsapp.call_args.args[1].startswith(b"%PDF"))

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
            "password1": "ClaveSegura123",
            "password2": "ClaveSegura123",
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


class InscripcionesTurnosTests(BaseProjectTestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username="admin-turnos",
            password="ClaveSegura123",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(
            usuario=self.user,
            hermandad=self.hermandad,
        )
        self.client.force_login(self.user)
        self.devoto = Devoto.objects.create(
            hermandad=self.hermandad,
            dpi="1234567890101",
            primer_nombre="Ana",
            primer_apellido="Prueba",
            fecha_nacimiento=date(1995, 8, 5),
            departamento="Sacatepéquez",
            municipio="Antigua Guatemala",
            celular="55555555",
            correo="ana@example.com",
            acepta_privacidad=True,
            acepta_email=True,
        )
        self.turnos = [
            TurnoRecorrido.objects.create(
                hermandad=self.hermandad,
                numero=numero,
                nombre_turno=f"Turno {numero}",
                pieza=f"Marcha {numero}",
                latitud=14.55,
                longitud=-90.73,
                orden_ruta=numero,
            )
            for numero in (1, 2)
        ]
        self.url = reverse(
            "web:inscripciones_turnos",
            kwargs={"slug": self.hermandad.slug},
        )

    def test_staff_can_register_multiple_turns_for_one_devoto(self):
        response = self.client.post(
            self.url,
            {
                "devoto_id": self.devoto.pk,
                "turno_ids": [turno.pk for turno in self.turnos],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(InscripcionTurno.objects.filter(devoto=self.devoto).count(), 2)
        self.assertTrue(
            InscripcionTurno.objects.filter(
                devoto=self.devoto,
                inscrito_por=self.user,
            ).exists()
        )

    def test_duplicate_turn_registration_does_not_create_a_second_record(self):
        InscripcionTurno.objects.create(devoto=self.devoto, turno=self.turnos[0])

        self.client.post(
            self.url,
            {
                "devoto_id": self.devoto.pk,
                "turno_ids": [self.turnos[0].pk],
            },
        )

        self.assertEqual(InscripcionTurno.objects.filter(devoto=self.devoto).count(), 1)

    def test_staff_cannot_register_a_devoto_from_another_organization(self):
        otra = Hermandad.objects.create(nombre="Otra", slug="otra")
        devoto_ajeno = Devoto.objects.create(
            hermandad=otra,
            dpi="1234567890102",
            primer_nombre="Luis",
            primer_apellido="Ajeno",
            fecha_nacimiento=date(1995, 8, 5),
            departamento="Sacatepéquez",
            municipio="Antigua Guatemala",
            celular="55555556",
            correo="luis@example.com",
            acepta_privacidad=True,
        )

        response = self.client.post(
            self.url,
            {
                "devoto_id": devoto_ajeno.pk,
                "turno_ids": [self.turnos[0].pk],
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(InscripcionTurno.objects.exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_delivery_is_audited_and_notifies_once_by_email(self):
        inscripcion = InscripcionTurno.objects.create(
            devoto=self.devoto,
            turno=self.turnos[0],
        )
        url = reverse(
            "web:entregar_turno",
            kwargs={
                "slug": self.hermandad.slug,
                "inscripcion_id": inscripcion.pk,
            },
        )

        first_response = self.client.post(url)
        inscripcion.refresh_from_db()
        entrega_registrada_en = inscripcion.entregado_en
        second_response = self.client.post(url)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertTrue(inscripcion.entregado)
        self.assertEqual(inscripcion.entregado_por, self.user)
        self.assertIsNotNone(entrega_registrada_en)
        self.assertEqual(mail.outbox.__len__(), 1)
        self.assertIn("Turno 1", mail.outbox[0].body)

    def test_staff_can_remove_delivered_enrollment(self):
        inscripcion = InscripcionTurno.objects.create(
            devoto=self.devoto,
            turno=self.turnos[0],
            entregado=True,
            entregado_en=timezone.now(),
            entregado_por=self.user,
        )
        response = self.client.get(
            self.url,
            {"codigo": self.devoto.comprobante_codigo},
        )
        self.assertContains(response, "Eliminar registro")

        clear_url = reverse(
            "web:limpiar_entrega_turno",
            kwargs={
                "slug": self.hermandad.slug,
                "inscripcion_id": inscripcion.pk,
            },
        )
        response = self.client.post(clear_url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(InscripcionTurno.objects.filter(pk=inscripcion.pk).exists())

    def test_clear_delivery_does_not_remove_pending_enrollment(self):
        inscripcion = InscripcionTurno.objects.create(
            devoto=self.devoto,
            turno=self.turnos[0],
        )
        clear_url = reverse(
            "web:limpiar_entrega_turno",
            kwargs={
                "slug": self.hermandad.slug,
                "inscripcion_id": inscripcion.pk,
            },
        )

        response = self.client.post(clear_url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(InscripcionTurno.objects.filter(pk=inscripcion.pk).exists())

    def test_scanning_qr_opens_staff_delivery_page_but_public_scan_stays_public(self):
        qr_url = reverse(
            "web:qr_devoto",
            kwargs={"codigo": self.devoto.comprobante_codigo},
        )

        staff_response = self.client.get(qr_url)
        self.assertEqual(staff_response.status_code, 302)
        self.assertIn(self.url, staff_response.url)
        self.assertIn(str(self.devoto.comprobante_codigo), staff_response.url)

        self.client.logout()
        public_response = self.client.get(qr_url)
        self.assertRedirects(
            public_response,
            reverse("web:hermandad_detalle", kwargs={"slug": self.hermandad.slug}),
        )

    def test_non_staff_cannot_access_registration_management(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("web:administrativo_login"), response.url)

    def test_registration_page_uses_organization_assigned_colors(self):
        self.hermandad.color_primario = "#4F7A5A"
        self.hermandad.color_acento = "#568765"
        self.hermandad.save(update_fields=["color_primario", "color_acento"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "--theme-header:#4F7A5A")
        self.assertContains(response, "--theme-topbar:#568765")
        self.assertContains(response, "--theme-button:#568765")

    def test_admin_page_provides_scanner_and_manual_devoto_search(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="openScanner"')
        self.assertContains(response, 'id="scannerVideo"')
        self.assertContains(response, "/static/web/vendor/jsQR.js")
        self.assertContains(response, "window.jsQR(image.data")
        self.assertContains(response, "Buscar devoto")
        self.assertContains(response, "Primero escanea el comprobante")

    def test_manual_search_finds_devoto_and_offers_turn_assignment(self):
        response = self.client.get(self.url, {"q": "ana"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.devoto.nombre_completo)
        self.assertContains(response, "Ver devoto y sus turnos")
        self.assertContains(response, str(self.devoto.comprobante_codigo))

    def test_selected_devoto_has_individual_turn_assignment_form(self):
        response = self.client.get(
            self.url,
            {"codigo": self.devoto.comprobante_codigo},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.devoto.nombre_completo)
        self.assertContains(response, "name=\"devoto_id\"")
        for turno in self.turnos:
            self.assertContains(response, f'value="{turno.pk}"')

    def test_devoto_panel_lists_registered_turns_and_delivery_state(self):
        cuenta = CuentaDevoto.objects.create(correo=self.devoto.correo)
        self.devoto.cuenta = cuenta
        self.devoto.save(update_fields=["cuenta"])
        InscripcionTurno.objects.create(
            devoto=self.devoto,
            turno=self.turnos[0],
            entregado=True,
            entregado_en=timezone.now(),
        )
        InscripcionTurno.objects.create(
            devoto=self.devoto,
            turno=self.turnos[1],
        )
        session = self.client.session
        session["cuenta_devoto_id"] = cuenta.pk
        session.save()

        response = self.client.get(reverse("web:devoto_panel"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mis turnos")
        self.assertContains(response, "Entregado el")
        self.assertContains(response, "Pendiente de entrega")


class AdminOnlyEditorTests(BaseProjectTestCase):
    def test_editor_redirects_anonymous_user_to_admin_login(self):
        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("web:administrativo_login"), response.url)

    def test_staff_user_can_open_editor(self):
        user = get_user_model().objects.create_user(
            username="staff",
            password="test-password-123",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)
        TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno 1",
            pieza="Marcha",
            latitud=14.55,
            longitud=-90.73,
            orden_ruta=1,
            alcanzado_en=timezone.now(),
        )
        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editor de turnos")
        self.assertContains(response, 'id="mapaEditor"')
        self.assertContains(response, 'name="numero"')
        self.assertContains(response, "draggable: true")
        self.assertContains(response, "function obtenerTurnoEnPunto")
        self.assertContains(response, 'marker.on("dragend"')
        self.assertNotContains(response, "Preparar turnos desde archivos")
        self.assertContains(response, "Cada arrastre crea como máximo un punto ajustable")
        self.assertContains(response, "simplificarRuta")
        self.assertContains(response, "function continuarArrastreLinea")
        self.assertContains(response, "Guardar línea")
        self.assertContains(response, "iniciarArrastreLinea")
        self.assertContains(response, 'id="turnoCambioDireccion"')
        self.assertContains(response, "#2563eb")
        self.assertContains(response, "#dc2626")
        self.assertContains(response, "Avance automático por GPS")
        self.assertContains(response, "Reiniciar progreso GPS")

    def test_staff_can_save_edited_route_line(self):
        user = get_user_model().objects.create_user(
            username="staff-rutas",
            password="staff-route-test",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)

        TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=2,
            nombre_turno="Turno de retorno",
            pieza="Marcha",
            latitud=14.56,
            longitud=-90.74,
            orden_ruta=0,
        )
        trazado = [[14.55, -90.73], [14.555, -90.735], [14.56, -90.74]]
        response = self.client.post(
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
            {
                "action": "guardar_trazado",
                "ruta_trazado": json.dumps(trazado),
                "turno_cambio_direccion": "2",
            },
        )

        self.assertRedirects(
            response,
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
        )
        self.hermandad.refresh_from_db()
        self.assertEqual(self.hermandad.ruta_trazado, trazado)
        self.assertEqual(self.hermandad.turno_cambio_direccion, 2)

    def test_moving_turn_updates_its_route_vertex_without_changing_other_points(self):
        user = get_user_model().objects.create_user(
            username="staff-mover-turno",
            password="staff-route-test",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)
        turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno 1",
            pieza="Marcha",
            latitud=14.55,
            longitud=-90.73,
            orden_ruta=0,
        )
        punto_intermedio = [14.555, -90.735]
        self.hermandad.ruta_trazado = [[14.55, -90.73], punto_intermedio, [14.56, -90.74]]
        self.hermandad.save(update_fields=["ruta_trazado"])

        response = self.client.post(
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
            {
                "turno_id": turno.id,
                "numero": 1,
                "orden_ruta": 0,
                "nombre_turno": "Turno 1",
                "pieza": "Marcha",
                "latitud": 14.551,
                "longitud": -90.731,
            },
        )

        self.assertRedirects(
            response,
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
        )
        turno.refresh_from_db()
        self.hermandad.refresh_from_db()
        self.assertEqual((turno.latitud, turno.longitud), (14.551, -90.731))
        self.assertEqual(
            self.hermandad.ruta_trazado,
            [[14.551, -90.731], punto_intermedio, [14.56, -90.74]],
        )

    def test_staff_cannot_save_route_with_unknown_direction_change_turn(self):
        user = get_user_model().objects.create_user(
            username="staff-cambio-invalido",
            password="ClaveSegura123",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)
        trazado = [[14.55, -90.73], [14.56, -90.74]]

        response = self.client.post(
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
            {
                "action": "guardar_trazado",
                "ruta_trazado": json.dumps(trazado),
                "turno_cambio_direccion": "99",
            },
        )

        self.assertRedirects(
            response,
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
        )
        self.hermandad.refresh_from_db()
        self.assertEqual(self.hermandad.ruta_trazado, [])
        self.assertIsNone(self.hermandad.turno_cambio_direccion)

    def test_deleting_last_turn_clears_saved_route_line(self):
        user = get_user_model().objects.create_user(
            username="staff-limpiar-ruta",
            password="staff-route-test",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)
        turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno final",
            pieza="Marcha de prueba",
            latitud=14.55,
            longitud=-90.73,
            orden_ruta=1,
        )
        self.hermandad.ruta_trazado = [[14.55, -90.73], [14.56, -90.74]]
        self.hermandad.turno_cambio_direccion = 1
        self.hermandad.save(update_fields=["ruta_trazado", "turno_cambio_direccion"])

        response = self.client.post(
            reverse(
                "web:eliminar_turno",
                kwargs={"slug": self.hermandad.slug, "turno_id": turno.pk},
            )
        )

        self.assertRedirects(
            response,
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
        )
        self.hermandad.refresh_from_db()
        self.assertEqual(self.hermandad.ruta_trazado, [])
        self.assertIsNone(self.hermandad.turno_cambio_direccion)
        self.assertFalse(TurnoRecorrido.objects.filter(hermandad=self.hermandad).exists())

    def test_staff_can_reset_gps_turn_progress(self):
        user = get_user_model().objects.create_user(
            username="staff-reiniciar-gps",
            password="ClaveSegura123",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)
        turno = TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=1,
            nombre_turno="Turno alcanzado",
            pieza="Marcha",
            latitud=14.55,
            longitud=-90.73,
            orden_ruta=1,
            alcanzado_en=timezone.now(),
        )
        self.hermandad.gps_ultimo_turno_en_zona_id = turno.pk
        self.hermandad.save(update_fields=["gps_ultimo_turno_en_zona_id"])

        response = self.client.post(
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
            {"action": "reiniciar_seguimiento"},
        )

        self.assertRedirects(
            response,
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
        )
        turno.refresh_from_db()
        self.hermandad.refresh_from_db()
        self.assertIsNone(turno.alcanzado_en)
        self.assertIsNone(self.hermandad.gps_ultimo_turno_en_zona_id)

    def test_public_tracking_view_receives_route_direction_turn(self):
        TurnoRecorrido.objects.create(
            hermandad=self.hermandad,
            numero=2,
            nombre_turno="Turno de retorno",
            pieza="Marcha",
            latitud=14.56,
            longitud=-90.74,
            orden_ruta=0,
        )
        self.hermandad.turno_cambio_direccion = 2
        self.hermandad.save(update_fields=["turno_cambio_direccion"])

        response = self.client.get(
            reverse("web:seguimiento", kwargs={"slug": self.hermandad.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["turno_cambio_direccion"], 2)
        self.assertContains(response, "Ida")
        self.assertContains(response, "Vuelta")
        self.assertContains(response, "dividirRutaPorTurno")

    def test_staff_cannot_save_edited_route_with_invalid_coordinates(self):
        user = get_user_model().objects.create_user(
            username="staff-rutas-invalidas",
            password="staff-route-test",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)
        response = self.client.post(
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
            {
                "action": "guardar_trazado",
                "ruta_trazado": json.dumps([[14.55, -90.73], [95, -90.74]]),
            },
        )

        self.assertRedirects(
            response,
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
        )
        self.hermandad.refresh_from_db()
        self.assertEqual(self.hermandad.ruta_trazado, [])

    def test_staff_cannot_save_turn_with_negative_route_order(self):
        user = get_user_model().objects.create_user(
            username="staff-orden-negativo",
            password="staff-route-test",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)
        response = self.client.post(
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
            {
                "numero": "1",
                "orden_ruta": "-1",
                "nombre_turno": "Turno de prueba",
                "pieza": "Marcha de prueba",
                "latitud": "14.55",
                "longitud": "-90.73",
            },
        )

        self.assertRedirects(
            response,
            reverse("web:editor_turnos", kwargs={"slug": self.hermandad.slug}),
        )
        self.assertFalse(TurnoRecorrido.objects.filter(hermandad=self.hermandad).exists())

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
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=nueva)
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
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=nueva)
        self.client.force_login(user)
        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": nueva.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, nueva.nombre)

    def test_staff_user_cannot_open_editor_of_another_organization(self):
        otra = Hermandad.objects.create(
            nombre="Otra organización",
            slug="otra-organizacion",
            activa=True,
        )
        user = get_user_model().objects.create_user(
            username="staff-limitado",
            password="test-password-123",
            is_staff=True,
        )
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=self.hermandad)
        self.client.force_login(user)

        response = self.client.get(reverse("web:editor_turnos", kwargs={"slug": otra.slug}))
        self.assertEqual(response.status_code, 403)

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
        AdministradorOrganizacion.objects.create(usuario=user, hermandad=soledad)
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


class AccessAndOrganizationTypeTests(TestCase):
    def setUp(self):
        self.hermandad = Hermandad.objects.create(
            nombre="Hermandad de prueba",
            slug="hermandad-login-prueba",
            tipo_organizacion=Hermandad.TIPO_HERMANDAD,
            activa=True,
        )
        self.cofradia = Hermandad.objects.create(
            nombre="Cofradía de prueba",
            slug="cofradia-musica-prueba",
            tipo_organizacion=Hermandad.TIPO_COFRADIA,
            activa=True,
        )

    def test_labels_and_shoulder_measurement_depend_on_organization_type(self):
        hermandad_response = self.client.get(
            reverse("web:seccion_generica", kwargs={"slug": self.hermandad.slug, "seccion": "marchas"})
        )
        cofradia_response = self.client.get(
            reverse("web:seccion_generica", kwargs={"slug": self.cofradia.slug, "seccion": "marchas"})
        )
        self.assertContains(hermandad_response, "Marchas")
        self.assertContains(cofradia_response, "Repertorio de música festiva")

        hermandad_registro = self.client.get(
            reverse("web:seccion_generica", kwargs={"slug": self.hermandad.slug, "seccion": "registro-actualizacion-datos"})
        )
        cofradia_registro = self.client.get(
            reverse("web:seccion_generica", kwargs={"slug": self.cofradia.slug, "seccion": "registro-actualizacion-datos"})
        )
        self.assertContains(hermandad_registro, 'id="id_medida_hombro_cm"')
        self.assertNotContains(cofradia_registro, 'id="id_medida_hombro_cm"')
        self.assertNotContains(cofradia_registro, "Medición visual")

    def test_devoto_can_login_and_sees_welcome_panel(self):
        cuenta = CuentaDevoto(correo="devoto@example.com")
        cuenta.set_password("ClaveSegura123")
        cuenta.save()
        Devoto.objects.create(
            cuenta=cuenta,
            hermandad=self.hermandad,
            dpi="1234567890123",
            primer_nombre="Pablo",
            primer_apellido="Prueba",
            fecha_nacimiento=date(2000, 1, 1),
            departamento="Sacatepéquez",
            municipio="Antigua Guatemala",
            celular="55555555",
            correo="devoto@example.com",
            acepta_privacidad=True,
        )
        response = self.client.post(
            reverse("web:devoto_login"),
            {"correo": "devoto@example.com", "password": "ClaveSegura123"},
        )
        self.assertRedirects(response, reverse("web:devoto_panel"))
        panel = self.client.get(reverse("web:devoto_panel"))
        self.assertEqual(panel.status_code, 200)
        self.assertContains(panel, "Bienvenido, Pablo Prueba")
        self.assertContains(panel, self.hermandad.nombre)
        self.assertContains(panel, "Preferencias de comunicación")

    def test_devoto_can_update_communication_preferences(self):
        cuenta = CuentaDevoto(correo="preferencias@example.com")
        cuenta.set_password("ClaveSegura123")
        cuenta.save()
        devoto = Devoto.objects.create(
            cuenta=cuenta,
            hermandad=self.hermandad,
            dpi="1234567890456",
            primer_nombre="María",
            primer_apellido="Prueba",
            fecha_nacimiento=date(1998, 1, 1),
            departamento="Sacatepéquez",
            municipio="Antigua Guatemala",
            celular="55556666",
            correo="preferencias@example.com",
            acepta_privacidad=True,
        )
        session = self.client.session
        session["cuenta_devoto_id"] = cuenta.pk
        session.save()

        response = self.client.post(
            reverse("web:devoto_preferencias_comunicacion", kwargs={"devoto_id": devoto.pk}),
            {"acepta_email": "on", "acepta_sms": "on", "acepta_whatsapp": "on"},
        )
        self.assertRedirects(response, reverse("web:devoto_panel"))
        devoto.refresh_from_db()
        self.assertTrue(devoto.acepta_email)
        self.assertFalse(devoto.acepta_sms)
        self.assertTrue(devoto.acepta_whatsapp)
        self.assertTrue(devoto.acepta_comunicaciones)
