from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from hermandades.models import Hermandad


class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = "weekly"

    def items(self):
        return ["web:home"]

    def location(self, item):
        return reverse(item)


class HermandadSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Hermandad.objects.filter(activa=True).order_by("nombre")

    def location(self, obj):
        return obj.get_absolute_url()


class SeccionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7
    secciones = [
        "mision-vision",
        "nuestras-imagenes",
        "templo",
        "agenda",
        "galeria-fotos",
        "galeria-filmica",
        "marchas",
    ]

    def items(self):
        return [
            (hermandad.slug, seccion)
            for hermandad in Hermandad.objects.filter(activa=True).only("slug")
            for seccion in self.secciones
        ]

    def location(self, item):
        slug, seccion = item
        return reverse("web:seccion_generica", kwargs={"slug": slug, "seccion": seccion})
