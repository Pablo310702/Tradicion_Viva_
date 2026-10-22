from django.shortcuts import render


def error_404(request, exception):
    return render(request, "web/errors/404.html", status=404)


def error_403(request, exception):
    return render(request, "web/errors/403.html", status=403)


def error_500(request):
    return render(request, "web/errors/500.html", status=500)
