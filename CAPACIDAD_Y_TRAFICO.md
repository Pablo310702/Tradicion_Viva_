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

### MediciÃ³n y ruta progresiva

La mediciÃ³n del 3 de noviembre de 2026 encontrÃ³ que el origen de Oracle tiene 1 vCPU, aproximadamente 5.6 GB de RAM, 4 GB de swap y 30 GB de disco (16 GB libres). La pÃ¡gina estÃ¡ sana con esa capacidad, pero ese tamaÃ±o no permite certificar 10,000 ni 30,000 usuarios simultÃ¡neos. El objetivo de 30,000 es una meta de arquitectura y pruebas, no una garantÃ­a automÃ¡tica.

Usa `tests/load/run_progressive_load.ps1` para ejecutar las pruebas Ãºnicamente contra un staging. El lanzador rechaza el dominio de producciÃ³n y detiene la progresiÃ³n cuando falla un perfil:

```powershell
.\tests\load\run_progressive_load.ps1 -BaseUrl https://staging.example.com -Profile step2
.\tests\load\run_progressive_load.ps1 -BaseUrl https://staging.example.com -RunAll
```

La ruta recomendada es: `step2` hasta 200 usuarios, `staged` hasta 10,000 y `stress` hasta 30,000. Antes de pasar de 200, hay que crear un staging aislado; antes de llegar a 10,000, escalarlo inicialmente a 4 vCPU y 16 GB de RAM, separar PostgreSQL y Redis, y poner al menos dos rÃ©plicas web detrÃ¡s de un balanceador. Cada escalÃ³n debe mantener p95 menor de 1.5 s, p99 menor de 3 s, menos de 1% de errores y sin saturaciÃ³n de CPU, memoria, PostgreSQL o Redis.

Los workers Gunicorn se pueden ajustar mediante `GUNICORN_WORKERS` y `GUNICORN_THREADS`, pero solo después de medir. Para superar de forma sostenida una carga alta, la siguiente evolución es separar PostgreSQL y Redis, usar almacenamiento de objetos para media/PDF y añadir una segunda instancia detrás de un balanceador.
