from django.db import models


class Hermandad(models.Model):
    nombre = models.CharField(max_length=200)
    templo = models.CharField(max_length=200, blank=True)
    ciudad = models.CharField(max_length=100, default="Antigua Guatemala")
    slug = models.SlugField(max_length=80, unique=True)
    descripcion_corta = models.CharField(max_length=255, blank=True)

    color_primario = models.CharField(max_length=20, default="#111111")
    color_acento = models.CharField(max_length=20, default="#b08d57")

    logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    portada = models.ImageField(upload_to="portadas/", null=True, blank=True)

    email_contacto = models.EmailField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)

    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class TurnoRecorrido(models.Model):
    hermandad = models.ForeignKey(
        Hermandad,
        on_delete=models.CASCADE,
        related_name="turnos_recorrido"
    )
    numero = models.PositiveIntegerField()
    nombre_turno = models.CharField(max_length=200)
    pieza = models.CharField(max_length=200)
    genero = models.CharField(max_length=100, blank=True)
    compositor = models.CharField(max_length=200, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    orden_ruta = models.PositiveIntegerField(default=0)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["numero", "orden_ruta"]
        unique_together = ("hermandad", "numero", "orden_ruta")

    def __str__(self):
        return f"{self.hermandad.nombre} - Turno {self.numero} - {self.pieza}"