from django.shortcuts import render


def error_404(request, exception):
    return render(request, "web/errors/404.html", status=404)


def error_403(request, exception):
    return render(request, "web/errors/403.html", status=403)


def error_500(request):
    return render(request, "web/errors/500.html", status=500)


def preview_error_403(request):
    """Vista pública para revisar visualmente la pantalla 403."""
    return error_403(request, None)


def preview_error_500(request):
    """Vista pública para revisar visualmente la pantalla 500 sin provocar una excepción."""
    return error_500(request)
