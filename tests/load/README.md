# Pruebas de carga de Tradición Viva

El escenario usa [k6](https://grafana.com/docs/k6/latest/) y prueba únicamente rutas públicas. El perfil por defecto es `smoke` para evitar generar una carga accidental.

## Perfiles

- `smoke`: hasta 20 usuarios virtuales.
- `step1`: escalón inicial hasta 1,000 usuarios virtuales.
- `step2`: escalón controlado hasta 200 usuarios virtuales.
- `staged`: sube gradualmente hasta 10,000 usuarios.
- `stress`: sube gradualmente hasta 30,000 usuarios; requiere un ambiente de pruebas o una autorización explícita.

## Ejecución local

```powershell
k6 run tests/load/tradicion_viva.k6.js
```

## Contra un ambiente de pruebas

```powershell
$env:BASE_URL = "https://staging.example.com"
$env:LOAD_PROFILE = "staged"
k6 run tests/load/tradicion_viva.k6.js
```

## Perfil de estrés

Ejecutarlo solo contra infraestructura propia y preparada para la prueba:

```powershell
$env:BASE_URL = "https://staging.example.com"
$env:LOAD_PROFILE = "stress"
k6 run tests/load/tradicion_viva.k6.js
```

El script falla si se intenta usar `stress` contra `tradicionviva.com.gt` sin definir `ALLOW_PRODUCTION_LOAD=true`. No se recomienda probar 30,000 usuarios directamente en producción.

## Qué observar

- `http_req_failed`: porcentaje de errores.
- `http_req_duration`: p95 y p99 de latencia.
- CPU, memoria y conexiones del servidor.
- Consultas y conexiones de PostgreSQL.
- Límites de Caddy/Nginx, workers de Django y pool de conexiones.
