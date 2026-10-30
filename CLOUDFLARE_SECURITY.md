# Configuración recomendada de Cloudflare

Esta aplicación debe pasar por Cloudflare en modo **Proxied** (nube naranja) para
que el WAF y los límites de tráfico se apliquen antes de llegar a Caddy/Gunicorn.
No se debe activar `Cache Everything` sobre páginas con sesión.

## DNS y origen

1. Crear registros `A` o `CNAME` para el dominio y los subdominios públicos.
2. Activar **Proxied** en los registros web.
3. Mantener PostgreSQL y Redis sin registros DNS públicos.
4. En el firewall de Oracle permitir HTTP/HTTPS únicamente desde los rangos IP
   oficiales de Cloudflare. El origen no debe aceptar tráfico directo de Internet.
5. En SSL/TLS usar **Full (strict)** y un certificado válido entre Cloudflare y
   Caddy.

## WAF y administración

En **Security > WAF > Custom rules**, crear una regla para `/admin/*`:

```text
(http.host eq "tradicionviva.com.gt" and starts_with(http.request.uri.path, "/admin/"))
```

La opción recomendada es permitir únicamente la IP fija de administración o,
mejor aún, proteger la ruta con Cloudflare Access/Zero Trust. Si todavía no se
conoce la IP administrativa, no se debe activar un bloqueo por IP porque podría
dejar fuera al propietario; se puede comenzar con Managed Challenge y cambiar a
Allow-list cuando la VPN esté lista.

## Límites de login

En **Security > WAF > Rate limiting rules**, crear límites separados para:

- `POST /admin/login/`: 10 solicitudes por IP cada 5 minutos; acción **Block**.
- `POST /iniciar-sesion/administrativo/`: 10 solicitudes por IP cada 5 minutos;
  acción **Block**.
- `POST /iniciar-sesion/devoto/`: 10 solicitudes por IP cada 5 minutos;
  acción **Managed Challenge** o **Block** según los falsos positivos.
- `POST /api/auth/login/`: comenzar con 20 solicitudes por IP por minuto y
  ajustar con los datos reales de uso.

Para login conviene contar únicamente respuestas `401` y `403` cuando el plan de
Cloudflare lo permita. Así no se penalizan usuarios que acceden correctamente.
Conservar también los límites internos de Django; son una segunda barrera si se
omite Cloudflare o si el tráfico llega desde una red compartida.

## Caché y rendimiento

Crear una Cache Rule para:

```text
(starts_with(http.request.uri.path, "/static/") or starts_with(http.request.uri.path, "/media/"))
```

Usar caché estándar y respetar el `Cache-Control` del origen. Crear una regla de
bypass para `/admin/*`, `/iniciar-sesion/*`, `/api/*` y cualquier solicitud que
contenga cookies de sesión. No cachear HTML autenticado, respuestas POST ni
respuestas que incluyan información personal.

## Verificación posterior

Después de activar las reglas, comprobar:

```text
curl -I https://tradicionviva.com.gt/
curl -I https://tradicionviva.com.gt/static/web/img/tradicion_viva_logo.png
curl -I https://tradicionviva.com.gt/admin/login/
```

La respuesta pública debe incluir CSP y Permissions-Policy, no debe revelar
`Server: gunicorn`, y los recursos estáticos deben mostrar caché. También hay que
probar manualmente login, CSRF, recuperación de contraseña y el panel admin desde
la IP/VPN autorizada.

