# Registro inicial de riesgos ISO — TRADICIÓN VIVA

> Registro inicial para revisión del responsable del proyecto. Debe actualizarse trimestralmente o después de un incidente.

| ID | Riesgo | Probabilidad | Impacto | Controles actuales | Acción pendiente | Responsable sugerido |
|---|---|---:|---:|---|---|---|
| R-001 | Exposición de DPI, correos, teléfonos o documentos | Media | Alto | HTTPS, CSRF, permisos y bucket privado previsto | Mapa de datos, retención, permisos y prueba de acceso | Privacidad |
| R-002 | Robo de `SECRET_KEY`, JWT o credenciales | Media | Alto | `.env` ignorado y variables de entorno | Gestor de secretos, rotación y revisión Git | Técnico |
| R-003 | Pérdida o corrupción de PostgreSQL | Media | Alto | Backups y PostgreSQL | Backup fuera de VPS, restauración mensual y RPO/RTO | Infraestructura |
| R-004 | Caída de Redis o bloqueo de rate limit | Media | Medio | Redis con healthcheck y Compose | Recuperación y comportamiento degradado | Técnico |
| R-005 | Acceso administrativo no autorizado | Media | Alto | Login, permisos y auditoría | MFA, revisión trimestral y bajas | Seguridad |
| R-006 | GPS externo indisponible o con datos antiguos | Alta | Medio | Rate limit y control de respuesta | Indicador de antigüedad y aviso operativo | Operaciones |
| R-007 | Fallo de despliegue o migración | Media | Alto | CI, migraciones, Docker y healthcheck | Backup previo, rollback y despliegue limpio | Técnico |
| R-008 | Multimedia maliciosa o excesivamente grande | Media | Medio | Validación y límites configurables | Escaneo, extensiones permitidas y bucket privado | Técnico |
| R-009 | Error humano en producción | Media | Alto | GitHub, pull requests y CI | Revisión obligatoria y checklist | Proyecto |
| R-010 | Incumplimiento de solicitudes de privacidad | Baja | Alto | Política y consentimiento parcial | Flujo de corrección, exportación y eliminación | Privacidad |

## Criterio de tratamiento

- **Alto:** requiere acción, responsable y evidencia antes del despliegue público.
- **Medio:** requiere control documentado y fecha de revisión.
- **Bajo:** debe registrarse y revisarse si cambia el contexto.

Cada riesgo cerrado debe conservar fecha, responsable, decisión, control aplicado, prueba, resultado y próxima revisión.
