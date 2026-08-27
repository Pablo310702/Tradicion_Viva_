# TRADICIÓN VIVA — Correcciones de accesos, tipos de organización y comunicaciones

## Cambios incluidos

1. **Inicio de sesión separado**
   - Selector público: `/iniciar-sesion/`.
   - Devotos: `/iniciar-sesion/devoto/` con correo y contraseña.
   - Administrativos: `/iniciar-sesion/administrativo/` con usuario/correo y contraseña; solo permite usuarios `is_staff`.
   - Panel del devoto: `/devoto/`, con mensaje de bienvenida, inscripciones y descarga de comprobantes.
   - Recuperación de contraseña por correo para cuentas de devotos.

2. **Hermandad y Cofradía ya no dependen del slug**
   - Se agregó `tipo_organizacion` al modelo `Hermandad`.
   - Valores: `Hermandad` o `Cofradía`.
   - Los registros existentes cuyo nombre inicia con “Cofradía” se clasifican automáticamente como cofradías al ejecutar la migración.

3. **Música según el tipo de organización**
   - Hermandad: la sección se muestra como **Marchas**.
   - Cofradía: la misma sección se muestra como **Repertorio de música festiva**.
   - Se conserva internamente la URL `/marchas/` para no romper enlaces existentes.

4. **Medición hasta el hombro solo para Hermandades**
   - El formulario de una Hermandad mantiene la medición visual.
   - En una Cofradía no aparece el campo, la cámara ni el resultado de medición.
   - El comprobante PDF solo muestra “MEDIDA HOMBRO” cuando la organización es Hermandad.

5. **Cuenta de devoto**
   - Al registrarse se solicita contraseña y confirmación.
   - Un mismo correo puede usar la misma cuenta para inscripciones en varias organizaciones.
   - Los registros antiguos sin cuenta pueden activarla usando “¿Olvidó su contraseña?” si conservan un correo válido.

6. **Comunicaciones masivas por correo, SMS y WhatsApp**
   - El devoto autoriza por separado correo, SMS y WhatsApp.
   - En el administrador existe **Comunicados masivos**.
   - Un comunicado puede enviarse a una organización específica o a todas.
   - Los SMS se integran con Twilio y WhatsApp con la API oficial WhatsApp Business Cloud de Meta.
   - Solo recibe cada canal quien lo autorizó expresamente.
   - Los estados e intentos quedan registrados en **Envíos de comunicados**.
   - Cada destinatario recibe un mensaje individual; no se muestran las direcciones de otros devotos.

## Envío de mensajes al teléfono

El número de celular se utiliza ahora para envíos reales por **SMS** y **WhatsApp** cuando se configuran credenciales válidas de Twilio y Meta en `.env`. Consulta `GUIA_SMS_WHATSAPP_TRADICION_VIVA.md` para la configuración completa.

## Configuración del correo

En `.env.example` se agregaron estas variables:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=usuario@example.com
EMAIL_HOST_PASSWORD=cambia-esta-clave
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=TRADICIÓN VIVA <usuario@example.com>
```

En desarrollo, si no se configura SMTP, Django usa el backend de consola y muestra los correos en la terminal.

## Cómo aplicar los cambios

Desde la carpeta del proyecto:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver
```

La migración nueva es:

`hermandades/migrations/0010_accesos_tipo_comunicados.py`

## Cómo enviar un comunicado

1. Entra por **Iniciar sesión → Administrativo**.
2. Abre **Comunicados masivos**.
3. Crea un comunicado con asunto y mensaje.
4. Selecciona una Hermandad/Cofradía o deja la organización vacía para todas.
5. Guarda.
6. En la lista de comunicados, selecciónalo.
7. Ejecuta la acción **“Enviar por los canales seleccionados en el comunicado”**.
8. El panel mostrará los aceptados y fallidos de correo, SMS y WhatsApp.
9. Consulta **Envíos de comunicados** para ver el detalle por destinatario y proveedor.

## Verificación realizada

- `python manage.py check`: sin errores.
- `python manage.py makemigrations --check --dry-run`: sin cambios pendientes.
- `python manage.py test`: 24 pruebas aprobadas.
