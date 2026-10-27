# Matriz de preparación ISO — TRADICIÓN VIVA

> Esta es una autoevaluación técnica y organizativa. No constituye una certificación ISO: la certificación requiere alcance definido, evidencias operativas y auditoría de un organismo certificador.

## Alcance evaluado

- Aplicación web Django de TRADICIÓN VIVA.
- Datos de hermandades, devotos, autenticación, comunicaciones y seguimiento GPS.
- Código fuente, CI de GitHub, PostgreSQL, Redis, almacenamiento multimedia y despliegue Docker/Caddy.

## Escala

- **Implementado:** existe control y evidencia revisable.
- **Parcial:** existe una parte técnica, pero falta procedimiento, prueba o evidencia operacional.
- **Pendiente:** debe implementarse antes de afirmar conformidad.
- **No evaluado:** requiere información del negocio o del proveedor.

## ISO/IEC 25010:2023 — calidad del producto de software

| Característica | Estado | Evidencia actual | Acción para cerrar brecha |
|---|---|---|---|
| Adecuación funcional | Parcial | Flujos de hermandades, devotos, agenda, multimedia y GPS | Mantener requisitos y criterios de aceptación por módulo |
| Eficiencia de desempeño | Pendiente | No hay línea base de tiempos ni carga | Medir p95 de páginas y API, y definir objetivos |
| Compatibilidad | Parcial | CI con PostgreSQL, Redis y Python 3.13 | Añadir matriz de navegadores y prueba móvil |
| Usabilidad | Parcial | Interfaz responsive y navegación por organización | Registrar pruebas con usuarios y accesibilidad |
| Fiabilidad | Parcial | Endpoint `/health/`, pruebas y healthchecks | Probar recuperación y documentar disponibilidad objetivo |
| Seguridad | Parcial | CSRF, cookies seguras, HSTS, rate limit, permisos y auditoría | Completar riesgos, revisión de accesos e incidentes |
| Mantenibilidad | Parcial | CI, migraciones verificadas y documentación | Añadir cobertura y análisis de dependencias |
| Flexibilidad | Parcial | Variables de entorno, Docker y almacenamiento S3-compatible | Probar despliegue limpio desde cero |
| Protección contra errores | Parcial | Validadores de formularios y manejo de errores | Ampliar pruebas de entradas inválidas y límites de archivos |

## ISO/IEC 27001:2022 — seguridad de la información

| Área de control | Estado | Evidencia actual | Brecha principal |
|---|---|---|---|
| Alcance y activos | Parcial | Aplicación, base de datos, Redis, GPS y multimedia identificados | Inventario formal de activos y responsables |
| Riesgos | Pendiente | Hay controles técnicos, pero no registro formal | Usar [ISO_RISK_REGISTER.md](./ISO_RISK_REGISTER.md) y revisarlo trimestralmente |
| Control de acceso | Parcial | Login, permisos administrativos y rutas protegidas | Revisar cuentas y permisos; documentar bajas |
| Secretos | Parcial | Variables de entorno y `.env` excluido del repositorio | Rotación documentada y gestor de secretos |
| Seguridad de aplicación | Parcial | CSRF, JWT, rate limit, validación y headers | Análisis de dependencias y pruebas de seguridad |
| Registro y trazabilidad | Parcial | `ActividadAdministrativa` y logging | Definir retención, acceso y revisión de logs |
| Proveedores | Pendiente | VPS, Caddy, S3/R2, correo, mensajería y GPS contemplados | Registrar proveedor, datos, disponibilidad y riesgos |
| Incidentes | Pendiente | No hay procedimiento formal | Crear respuesta, comunicación y cierre de incidentes |
| Continuidad | Parcial | PostgreSQL, Redis, backups y Docker Compose | Probar restauración y documentar RPO/RTO |
| Mejora continua | Parcial | CI en cada push y pull request | Registrar hallazgos y acciones correctivas |

## ISO/IEC 27701:2025 — privacidad

La aplicación procesa DPI, nombres, correo, teléfono y ubicación GPS.

| Tema | Estado | Pendiente |
|---|---|---|
| Inventario de datos personales | Parcial | Mapa de DPI, nombre, correo, teléfono, ubicación y documentos |
| Finalidad y base del tratamiento | Parcial | Relacionar cada campo con finalidad y consentimiento |
| Retención y eliminación | Pendiente | Definir plazos y anonimización |
| Derechos de los titulares | Pendiente | Exportación, corrección, eliminación e información |
| Encargados externos | Pendiente | Registro de VPS, correo, mensajería, GPS y almacenamiento |
| Privacidad desde el diseño | Parcial | Consentimientos y controles de acceso existentes | Documentar decisiones por cambio importante |

## ISO 22301:2019 — continuidad del negocio

| Control | Estado | Acción |
|---|---|---|
| Copias de seguridad | Parcial | Mantener backup diario y una copia fuera de la VPS |
| Restauración | Pendiente | Ejecutar restauración mensual y guardar evidencia |
| RPO/RTO | Pendiente | Definir pérdida y tiempo máximos aceptables |
| Dependencias críticas | Parcial | PostgreSQL, Redis, GPS, correo, mensajería y bucket identificados | Documentar alternativas o impacto |
| Recuperación ante desastre | Pendiente | Crear runbook de reconstrucción desde Docker y backups |

## ISO 9001:2026 — gestión de calidad

ISO 9001 aplica principalmente a la organización y sus procesos, no solo al código. Actualmente no hay evidencia suficiente de un sistema de gestión de calidad formal.

Pendientes: objetivos medibles, responsables, control de cambios, gestión de quejas, revisión de resultados, auditorías internas y acciones correctivas.

## Evidencias actuales del repositorio

- `web/tests.py`: 70 pruebas declaradas.
- `.github/workflows/ci.yml`: PostgreSQL, Redis, migraciones y `check --deploy`.
- `config/settings.py`: seguridad, secretos por entorno, logging, rate limit y S3.
- `web/audit.py`: registro de actividad administrativa.
- `DEPLOYMENT_SECURITY.md`: controles de despliegue seguro.
- `Dockerfile`, `docker-compose.production.yml` y `Caddyfile`: paquete reproducible.
- `DEPLOYMENT_DOCKER.md`: operación y despliegue.
- [ISO_RISK_REGISTER.md](./ISO_RISK_REGISTER.md): riesgos iniciales.

## Criterio interno para declarar “preparado para auditoría”

1. Cero secretos reales en el repositorio y rotación documentada.
2. `manage.py check --deploy` sin advertencias no aceptadas.
3. CI verde en cada cambio.
4. Restauración de backup ejecutada y registrada.
5. Inventario de activos, datos personales, proveedores y riesgos actualizado.
6. Prueba de incidentes y recuperación ejecutada.
7. Revisión de usuarios y permisos documentada.
8. Métricas de calidad, disponibilidad, errores y tiempos registradas.

## Próxima prioridad

Cerrar ISO/IEC 27001 e ISO/IEC 27701 antes del despliegue público, porque el sistema procesa credenciales, DPI, datos de contacto y ubicación GPS.
