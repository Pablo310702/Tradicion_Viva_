from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from web.media_views import media_file
from web.sitemaps import (
    HermandadSitemap,
    SeccionSitemap,
    StaticViewSitemap,
)

handler404 = "web.error_views.error_404"
handler403 = "web.error_views.error_403"
handler500 = "web.error_views.error_500"


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
    urlpatterns += [
        path(
            f"{settings.MEDIA_URL.lstrip('/')}<path:path>",
            media_file,
            name="media-file",
        ),
    ]
