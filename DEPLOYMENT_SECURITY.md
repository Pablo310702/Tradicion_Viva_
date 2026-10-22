# Despliegue seguro de TRADICIÓN VIVA

La aplicación incluye límites de abuso para login, recuperación de contraseña y API.
En producción configura `REDIS_URL` para compartirlos entre procesos e instancias.

## Variables mínimas de producción

```env
DEBUG=False
SECRET_KEY=<clave-aleatoria-larga-y-privada>
JWT_SECRET_KEY=<otra-clave-aleatoria-larga-y-privada>
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com,https://www.tu-dominio.com
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
DATABASE_SSL_REQUIRE=True
REDIS_URL=rediss://<usuario>:<clave>@<host>:6379/0
TRUST_CLOUDFLARE_IP_HEADER=True
MEDIA_STORAGE_BACKEND=s3
AWS_QUERYSTRING_AUTH=True
```

Guarda estas variables únicamente como secretos del proveedor de hosting. No las
copies al repositorio ni las compartas en capturas o chats.

## Cloudflare

1. Añade el dominio a Cloudflare y cambia en el registrador los nameservers por los
   indicados por Cloudflare.
2. Crea los registros DNS `A`, `AAAA` o `CNAME` que indique el hosting.
3. Activa SSL/TLS en modo `Full (strict)`.
4. Activa HTTPS automático y HSTS después de verificar el certificado.
5. Configura reglas WAF/rate limit para `/admin/*`, `/iniciar-sesion/*`,
   `/api/auth/*` y `/devoto/recuperar-contrasena/*`.
6. Mantén protegidos los webhooks de Twilio y Meta mediante sus firmas; no los dejes
   expuestos a reglas genéricas que bloqueen proveedores legítimos.

## Hosting

El proyecto parece preparado para un proveedor tipo Render por el uso de
`RENDER_EXTERNAL_HOSTNAME`. Para producción usa PostgreSQL, Redis administrado,
almacenamiento privado S3 compatible y HTTPS automático. El servidor de aplicación
no debe exponerse directamente a Internet sin CDN/WAF.

## Verificación antes de publicar

```text
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
```

Prueba también restauración de backups, recuperación de contraseña, webhooks firmados,
rotación de secretos y límites de archivos.
