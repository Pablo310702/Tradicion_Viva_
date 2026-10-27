# Declaración de aplicabilidad inicial — TRADICIÓN VIVA

> Documento de preparación para ISO/IEC 27001. No es una declaración aprobada ni una certificación. Debe ser revisado por el responsable del proyecto y actualizado cuando cambie el alcance o el riesgo.

## Alcance

El alcance inicial comprende la aplicación Django, sus usuarios administrativos y devotos, PostgreSQL, Redis, almacenamiento multimedia, GPS, correo/mensajería, VPS, Docker/Caddy y repositorio GitHub.

## Criterio

- **Aplicable:** el control debe existir porque el sistema procesa información o depende de él.
- **Aplicable parcial:** existe una parte técnica, pero falta operación o evidencia.
- **Pendiente:** debe implementarse antes de la auditoría.
- **No aplicable:** solo puede marcarse así con una justificación documentada.

| Control / tema | Estado | Evidencia o implementación | Próximo paso |
|---|---|---|---|
| Política de seguridad | Parcial | `DEPLOYMENT_SECURITY.md` | Aprobar versión, responsable y fecha de revisión |
| Roles y responsabilidades | Pendiente | Responsables sugeridos en registro de riesgos | Nombrar responsable técnico, privacidad y operaciones |
| Inventario de activos | Parcial | Aplicación, VPS, DB, Redis, S3/R2, GPS y CI identificados | Crear inventario con propietario y criticidad |
| Gestión de riesgos | Parcial | `ISO_RISK_REGISTER.md` | Valorar riesgos con el equipo y registrar tratamiento |
| Gestión de accesos | Parcial | Login, permisos y rutas protegidas | Revisar usuarios trimestralmente y documentar bajas |
| Secretos y credenciales | Parcial | Variables de entorno y `.gitignore` | Usar gestor de secretos y rotación periódica |
| Seguridad en desarrollo | Parcial | Pull requests, CI y migraciones verificadas | Añadir análisis de dependencias y secretos |
| Registro de eventos | Parcial | `ActividadAdministrativa` y logging | Definir retención, integridad y revisión |
| Backups | Parcial | Comando de respaldo diario | Copia fuera de VPS y prueba de restauración |
| Continuidad | Pendiente | Docker Compose y healthchecks | Definir RPO/RTO y procedimiento de recuperación |
| Proveedores | Pendiente | VPS, S3/R2, GPS, correo y mensajería identificados | Registrar contrato, datos, SLA y riesgos |
| Incidentes | Pendiente | No existe runbook formal | Usar `SECURITY_INCIDENT_RESPONSE.md` |
| Privacidad | Parcial | Consentimientos y política existentes | Completar inventario, retención y derechos |
| Seguridad física | No evaluado | Depende del proveedor de VPS y almacenamiento | Solicitar evidencias del proveedor |
| Cumplimiento legal | No evaluado | Requiere revisión jurídica local | Confirmar obligaciones aplicables en Guatemala |

## Decisiones actuales

- HSTS preload permanece desactivado hasta validar todos los subdominios.
- El almacenamiento multimedia de producción debe ser S3/R2/compatible y privado cuando contenga datos personales.
- El servicio Django no debe exponerse directamente a Internet; Caddy debe ser el punto público.
- Las excepciones y riesgos aceptados deben tener responsable, fecha de vencimiento y justificación.
