# Despliegue de TRADICIÓN VIVA en una VPS

Este paquete está pensado para una VPS económica con Docker Compose. No usa Render.

## 1. Dominio y subdominios

Usa un dominio base, por ejemplo `tradicionviva.com`, y crea en el DNS:

```text
@         A       IP_PUBLICA_DE_LA_VPS
www       CNAME   tradicionviva.com
rosario   CNAME   tradicionviva.com
san-jose  CNAME   tradicionviva.com
perdon    CNAME   tradicionviva.com
soledad   CNAME   tradicionviva.com
venerada  CNAME   tradicionviva.com
calvario  CNAME   tradicionviva.com
```

Los nombres de los seis subdominios se pueden cambiar sin tocar la base de datos. Coloca esos nombres, separados por comas, en `CADDY_SITES`; Caddy obtiene los certificados HTTPS automáticamente para cada nombre incluido.

## 2. Variables

```bash
cp .env.production.example .env.production
```

Edita `.env.production`, especialmente las claves, contraseñas, dominio y datos del bucket S3/R2. Para `ALLOWED_HOSTS`, Django usa `.tradicionviva.com` para incluir sus subdominios; `*.tradicionviva.com` no debe usarse ahí como sustituto.

Se deja `SECURE_HSTS_PRELOAD=False` deliberadamente. Solo se cambia a `True` después de comprobar que el dominio base y todos los subdominios responden siempre por HTTPS.

## 3. Arranque

```bash
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
curl -f https://tradicionviva.com/health/
```

La primera ejecución aplica migraciones, recopila estáticos y luego levanta Django detrás de Caddy. El endpoint `/health/` responde `{"status":"ok"}` y no depende de una sesión de usuario.

## 4. Archivos multimedia

`MEDIA_STORAGE_BACKEND=s3` hace que las nuevas imágenes y videos se guarden en el bucket configurado, no en el disco efímero de la aplicación. Antes de abrir el sitio al público, hay que copiar al bucket el contenido multimedia existente de `media/` y verificar las URLs firmadas. El bucket debe ser privado si contiene documentos de devotos.

## 5. Operación básica

```bash
docker compose -f docker-compose.production.yml logs -f web
docker compose -f docker-compose.production.yml restart web
docker compose -f docker-compose.production.yml pull
```
