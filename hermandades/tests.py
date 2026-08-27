from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Hermandad, MarchaProcesional, VideoHermandad


class ContentModelTests(TestCase):
    def setUp(self):
        self.hermandad = Hermandad.objects.create(
            nombre="Hermandad de prueba",
            slug="hermandad-prueba",
        )

    def test_marcha_requires_audio_or_link(self):
        marcha = MarchaProcesional(hermandad=self.hermandad, titulo="Marcha")
        with self.assertRaises(ValidationError):
            marcha.full_clean()

    def test_youtube_url_is_converted_to_privacy_embed(self):
        video = VideoHermandad(
            hermandad=self.hermandad,
            titulo="Video",
            url="https://www.youtube.com/watch?v=abcdefghijk",
        )
        self.assertEqual(
            video.embed_url,
            "https://www.youtube-nocookie.com/embed/abcdefghijk",
        )

from datetime import date
from unittest.mock import Mock

from django.test import override_settings

from .messaging import (
    normalizar_telefono_e164,
    send_sms_twilio,
    send_whatsapp_meta,
)
from .models import Comunicado, Devoto


class MessagingServiceTests(TestCase):
    def setUp(self):
        self.hermandad = Hermandad.objects.create(
            nombre="Hermandad Mensajería",
            slug="hermandad-mensajeria",
        )
        self.devoto = Devoto.objects.create(
            hermandad=self.hermandad,
            dpi="1234567890123",
            primer_nombre="Ana",
            primer_apellido="Prueba",
            fecha_nacimiento=date(1995, 1, 1),
            departamento="Sacatepéquez",
            municipio="Antigua Guatemala",
            celular="5555-5555",
            correo="ana@example.com",
            acepta_privacidad=True,
            acepta_sms=True,
            acepta_whatsapp=True,
        )

    @override_settings(DEFAULT_PHONE_COUNTRY_CODE="+502")
    def test_normaliza_numero_guatemalteco_a_e164(self):
        self.assertEqual(normalizar_telefono_e164("5555-5555"), "+50255555555")
        self.assertEqual(normalizar_telefono_e164("+502 5555 5555"), "+50255555555")

    @override_settings(
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="secret",
        TWILIO_API_KEY_SID="",
        TWILIO_API_KEY_SECRET="",
        TWILIO_FROM_NUMBER="+15005550006",
        TWILIO_MESSAGING_SERVICE_SID="",
        TWILIO_STATUS_CALLBACK_URL="",
        PUBLIC_BASE_URL="",
        MESSAGING_HTTP_TIMEOUT=5,
    )
    def test_sms_twilio_envia_por_api(self):
        response = Mock(status_code=201, ok=True)
        response.json.return_value = {"sid": "SM123", "status": "queued"}
        session = Mock()
        session.post.return_value = response

        result = send_sms_twilio("+50255555555", "Mensaje de prueba", session=session)

        self.assertEqual(result.message_id, "SM123")
        self.assertEqual(result.provider, "twilio")
        args, kwargs = session.post.call_args
        self.assertIn("/Accounts/AC123/Messages.json", args[0])
        self.assertEqual(kwargs["data"]["To"], "+50255555555")
        self.assertEqual(kwargs["data"]["From"], "+15005550006")

    @override_settings(
        WHATSAPP_ACCESS_TOKEN="token-meta",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        WHATSAPP_GRAPH_API_VERSION="v25.0",
        WHATSAPP_DEFAULT_TEMPLATE_NAME="tradicion_viva_comunicado",
        WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE="es",
        MESSAGING_HTTP_TIMEOUT=5,
    )
    def test_whatsapp_meta_envia_plantilla_con_nombre_y_mensaje(self):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        session = Mock()
        session.post.return_value = response

        result = send_whatsapp_meta(
            "+50255555555",
            "Información importante",
            first_name="Ana",
            mode=Comunicado.WHATSAPP_MODO_PLANTILLA,
            template_name="",
            template_language="es",
            template_param_mode=Comunicado.WHATSAPP_PARAM_NOMBRE_MENSAJE,
            session=session,
        )

        self.assertEqual(result.message_id, "wamid.123")
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "tradicion_viva_comunicado")
        parameters = payload["template"]["components"][0]["parameters"]
        self.assertEqual(parameters[0]["text"], "Ana")
        self.assertEqual(parameters[1]["text"], "Información importante")
