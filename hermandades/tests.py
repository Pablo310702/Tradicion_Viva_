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
