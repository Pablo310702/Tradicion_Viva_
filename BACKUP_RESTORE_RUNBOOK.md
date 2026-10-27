# Runbook de backup y restauración

## Objetivo

Garantizar que una copia de seguridad de TRADICIÓN VIVA pueda restaurarse y verificarse, no solo que exista un archivo.

## Política inicial

- Backup diario de PostgreSQL.
- Copia fuera de la VPS.
- Cifrado en tránsito y reposo.
- Retención mínima definida por el responsable del proyecto.
- Prueba de restauración mensual y después de cambios importantes.
- No guardar secretos dentro del backup sin cifrado.

## Prueba de restauración

1. Crear un entorno aislado; nunca restaurar directamente sobre producción.
2. Obtener la copia identificada por fecha y checksum.
3. Levantar PostgreSQL compatible.
4. Restaurar la base de datos.
5. Levantar la aplicación con variables de prueba.
6. Ejecutar migraciones pendientes de forma controlada.
7. Verificar `/health/`, inicio de sesión, organizaciones, registros, multimedia y GPS simulado.
8. Comparar conteos y registros críticos con el origen.
9. Medir tiempo de recuperación.
10. Registrar resultado, fallos y acción correctiva.

## Evidencia

```text
Fecha:
Identificador de backup:
Checksum:
Entorno de prueba:
Hora de inicio:
Hora de finalización:
RPO observado:
RTO observado:
Pruebas ejecutadas:
Resultado:
Problemas:
Responsable:
```
