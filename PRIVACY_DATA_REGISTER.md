# Registro de datos personales — TRADICIÓN VIVA

> Plantilla operativa para completar antes del despliegue público. No incluir valores reales de personas en este documento.

| Categoría | Ejemplos | Finalidad | Acceso | Retención propuesta | Eliminación |
|---|---|---|---|---|---|
| Identificación | DPI, nombres, fecha de nacimiento | Registro y validación del devoto | Devoto autorizado y organización correspondiente | Definir con responsable | Solicitud validada y política de retención |
| Contacto | Correo, teléfono | Acceso y comunicaciones autorizadas | Devoto y personal autorizado | Definir | Anonimizar o eliminar al vencer finalidad |
| Cuenta | Usuario, hash de contraseña, tokens | Autenticación y seguridad | Sistema y administradores limitados | Mientras exista cuenta + plazo definido | Revocación y eliminación segura |
| Ubicación | GPS, recorrido, fecha y hora | Seguimiento procesional autorizado | Solo usuarios con permiso | Definir por evento | Purga o anonimización |
| Multimedia | Fotografías, videos, documentos | Contenido institucional o registro | Según visibilidad del archivo | Definir por tipo | Eliminación desde almacenamiento y DB |
| Auditoría | Acciones, IP, fecha, objeto afectado | Seguridad y trazabilidad | Responsables autorizados | Definir periodo legal/operativo | Eliminación controlada |

## Reglas mínimas

- No guardar más datos de los necesarios para la finalidad declarada.
- No poner DPI, documentos ni GPS privado en URLs públicas.
- Mantener el bucket de producción privado por defecto.
- Registrar consentimiento y su versión.
- Permitir solicitudes de acceso, corrección y eliminación mediante un responsable identificado.
- Revisar este registro al agregar un campo o integración externa.
