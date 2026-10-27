# Procedimiento de respuesta a incidentes

## Objetivo

Detectar, contener, investigar, recuperar y documentar incidentes que afecten la confidencialidad, integridad o disponibilidad de TRADICIÓN VIVA.

## Incidentes incluidos

- Acceso administrativo no autorizado.
- Exposición de DPI, documentos, correos, teléfonos o GPS.
- Robo de secretos, tokens o credenciales.
- Malware o archivo multimedia peligroso.
- Pérdida de base de datos o backup.
- Caída prolongada de VPS, PostgreSQL, Redis, GPS o almacenamiento.

## Prioridad

- **P1 crítico:** datos personales expuestos, cuenta administrativa comprometida o pérdida de servicio general.
- **P2 alto:** vulnerabilidad explotable, proveedor crítico caído o corrupción parcial.
- **P3 medio:** error limitado sin evidencia de exposición.
- **P4 bajo:** hallazgo preventivo sin impacto actual.

## Pasos obligatorios

1. Registrar fecha, persona que detectó, sistemas afectados y evidencia disponible.
2. Confirmar el incidente sin modificar ni borrar logs.
3. Contener: bloquear cuenta, revocar token, aislar archivo, limitar endpoint o retirar servicio comprometido.
4. Rotar secretos relacionados y preservar evidencia.
5. Determinar datos, personas y proveedores afectados.
6. Recuperar desde una copia verificada si es necesario.
7. Validar `/health/`, login, base de datos, archivos y GPS.
8. Documentar causa raíz, impacto y acciones correctivas.
9. Comunicar a responsables y, si corresponde, a titulares o autoridades según la obligación legal aplicable.
10. Cerrar solo cuando exista evidencia de corrección y una fecha de seguimiento.

## Registro de incidente

```text
ID:
Fecha/hora de detección:
Reportado por:
Prioridad:
Sistemas afectados:
Datos afectados:
Contención aplicada:
Secretos rotados:
Evidencia preservada:
Comunicación realizada:
Causa raíz:
Acción correctiva:
Responsable:
Fecha de cierre:
Fecha de revisión:
```
