from django.db import connection
from django.urls import Resolver404, resolve

from hermandades.models import AdministradorOrganizacion, Hermandad


class OrganizationContextMiddleware:
    """Sets PostgreSQL RLS context for the current request."""

    organization_setting = "app.current_organization_id"
    account_setting = "app.current_account_id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if connection.vendor != "postgresql":
            return self.get_response(request)

        organization_id, account_id = self._context_for_request(request)
        self._set_context(organization_id, account_id)
        try:
            return self.get_response(request)
        finally:
            self._set_context("", "")

    def _context_for_request(self, request):
        organization_id = ""
        account_id = ""

        # La cuenta de devoto usa una sesiÃ³n propia y no convierte al usuario
        # en un django.contrib.auth User. Por eso este contexto debe cargarse
        # independientemente de request.user.is_authenticated.
        account_id = str(request.session.get("cuenta_devoto_id", ""))

        if request.user.is_authenticated:
            if request.user.is_superuser:
                organization_id = "*"
            elif request.user.is_staff:
                organization_id = str(
                    AdministradorOrganizacion.objects.filter(
                        usuario_id=request.user.pk,
                        activo=True,
                    ).values_list("hermandad_id", flat=True).first()
                    or ""
                )

        if not organization_id:
            organization_id = self._organization_from_url(request)

        return organization_id, account_id

    @staticmethod
    def _organization_from_url(request):
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return ""

        slug = match.kwargs.get("slug")
        if not slug:
            return ""
        return str(
            Hermandad.objects.filter(slug__iexact=slug).values_list("pk", flat=True).first()
            or ""
        )

    def _set_context(self, organization_id, account_id):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config(%s, %s, false), set_config(%s, %s, false)",
                [
                    self.organization_setting,
                    organization_id,
                    self.account_setting,
                    account_id,
                ],
            )
