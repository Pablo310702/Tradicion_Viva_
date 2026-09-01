from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from web.sitemaps import (
    HermandadSitemap,
    SeccionSitemap,
    StaticViewSitemap,
)


# =========================================================
# SITEMAPS
# =========================================================

sitemaps = {
    "static": StaticViewSitemap,
    "hermandades": HermandadSitemap,
    "secciones": SeccionSitemap,
}


# =========================================================
# RUTAS PRINCIPALES
# =========================================================

urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),

    path("", include("web.urls")),
]


# =========================================================
# ARCHIVOS MEDIA EN DESARROLLO
# =========================================================

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    ) 