# Capacidad y tráfico

## Estado actual

La aplicación usa Caddy, Gunicorn, PostgreSQL y Redis en Docker. El tráfico público pasa por Cloudflare. Los archivos estáticos tienen caché de larga duración; el contenido dinámico, sesiones, formularios, administración y comprobantes PDF no se cachean de forma global.

No se debe convertir toda la página en `Cache Everything`: podría entregar HTML de otra sesión o un comprobante equivocado.

## Cloudflare

1. Mantener el proxy naranja activo para los hosts públicos.
2. Revisar `Analytics > Traffic` para requests, page views, bandwidth, errores 5xx, cache hit ratio y tráfico al origen.
3. Crear reglas de caché solo para contenido público anónimo, nunca para `/admin/`, `/iniciar-sesion/`, formularios, `/api/`, cookies de sesión ni PDFs personalizados.
4. Mantener la protección DDoS administrada en su configuración predeterminada.
5. Aplicar rate limiting únicamente a login, recuperación de contraseña, APIs y altas públicas. No limitar globalmente todas las visitas.
6. Cuando el origen esté estable, restringir Oracle para aceptar 80/443 solo desde IPs de Cloudflare; conservar SSH restringido a la IP administrativa.

## Pruebas

La prueba de carga de `tests/load/tradicion_viva.k6.js` se ejecuta contra un staging equivalente. La secuencia recomendada es `step2`, `staged` y después `stress`, observando CPU, memoria, swap, workers, PostgreSQL, Redis, 5xx y latencias p95/p99.

10,000 visitantes distribuidos en el día no equivalen a 10,000 usuarios simultáneos. La capacidad solo se certifica cuando el escalón pasa los umbrales de `tests/load/README.md` sin degradación ni reinicios.

## Escalado

Los workers Gunicorn se pueden ajustar mediante `GUNICORN_WORKERS` y `GUNICORN_THREADS`, pero solo después de medir. Para superar de forma sostenida una carga alta, la siguiente evolución es separar PostgreSQL y Redis, usar almacenamiento de objetos para media/PDF y añadir una segunda instancia detrás de un balanceador.
