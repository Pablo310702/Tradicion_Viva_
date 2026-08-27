# TRADICIÓN VIVA — Guía de correo, SMS y WhatsApp automáticos

## 1. Qué quedó implementado

El sistema ya contiene una capa de comunicaciones masivas con tres canales independientes:

- **Correo electrónico:** SMTP de Django.
- **SMS:** Twilio Programmable Messaging.
- **WhatsApp:** API oficial **WhatsApp Business Cloud de Meta**.

Cada devoto autoriza por separado **Correo**, **SMS** y **WhatsApp**. El sistema solo incluye en cada envío a los registros que autorizaron ese canal. El devoto puede cambiar esas preferencias desde **Mi cuenta > Preferencias de comunicación**.

En Django Admin se agregó:

- selección de una hermandad/cofradía o todas las organizaciones;
- selección de canales;
- mensaje personalizado con marcadores;
- envío masivo por todos los canales seleccionados o por un solo canal;
- contadores de aceptados/fallidos por canal;
- historial individual en **Envíos de comunicados**;
- actualización de estado mediante webhooks de Twilio y Meta cuando el proyecto está publicado en una URL HTTPS.

## 2. Antes de ejecutar

En la carpeta del proyecto:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

También puedes ejecutar el asistente:

```powershell
python configurar_mensajeria.py
```

El asistente actualiza las variables de mensajería en `.env`. Si `.env` ya existe, crea `.env.bak` antes de modificarlo.

Para revisar la configuración sin enviar mensajes:

```powershell
python verificar_mensajeria.py
```

Para comprobar además las credenciales contra Twilio y Meta **sin enviar mensajes**:

```powershell
python verificar_mensajeria.py --network
```

---

## 3. Configurar SMS con Twilio

### Datos necesarios

Necesitas una cuenta de Twilio y un remitente autorizado para SMS. Obtén en la consola de Twilio:

- `Account SID`
- `Auth Token` para pruebas/local, o una `API Key SID` + `API Key Secret` para producción
- un número de Twilio habilitado para SMS **o** un `Messaging Service SID`

Documentación oficial: <https://www.twilio.com/docs/messaging>

### Variables `.env`

Ejemplo con número remitente:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=+1XXXXXXXXXX
TWILIO_MESSAGING_SERVICE_SID=
```

Ejemplo usando Messaging Service:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=
TWILIO_MESSAGING_SERVICE_SID=MGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Para producción puedes utilizar API Key:

```env
TWILIO_API_KEY_SID=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Aunque uses API Key para enviar, conserva `TWILIO_AUTH_TOKEN` en el servidor si activarás el webhook de estados: Twilio usa ese Auth Token para validar la firma `X-Twilio-Signature`.

El código envía el SMS mediante:

`POST https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json`

Los celulares locales de Guatemala de 8 dígitos se convierten automáticamente a `+502XXXXXXXX`.

> **Importante:** un SMS largo puede dividirse en varios segmentos y el proveedor puede cobrar cada segmento.

---

## 4. Configurar WhatsApp oficial de Meta

### Datos necesarios

Necesitas:

1. un portafolio empresarial de Meta;
2. una WhatsApp Business Account (WABA);
3. un número registrado en WhatsApp Business Platform;
4. `Phone Number ID`;
5. un `Access Token` con los permisos correspondientes de WhatsApp Business;
6. para producción, una plantilla aprobada por Meta para comunicaciones iniciadas por la organización.

Colección oficial de Meta en Postman: <https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api>

### Variables `.env`

```env
WHATSAPP_GRAPH_API_VERSION=v25.0
WHATSAPP_ACCESS_TOKEN=TU_ACCESS_TOKEN
WHATSAPP_PHONE_NUMBER_ID=TU_PHONE_NUMBER_ID
WHATSAPP_DEFAULT_TEMPLATE_NAME=tradicion_viva_comunicado
WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE=es
```

### Plantilla recomendada

En WhatsApp Manager crea y solicita aprobación de una plantilla llamada:

`tradicion_viva_comunicado`

Idioma sugerido: `es`

Cuerpo sugerido:

```text
Hola {{1}},

{{2}}

TRADICIÓN VIVA
```

Dentro de Django Admin selecciona **2 variables: nombre + mensaje**.

El sistema enviará:

- `{{1}}` = primer nombre del devoto;
- `{{2}}` = contenido del comunicado.

### Probar con `hello_world`

Si estás usando el entorno de prueba de Meta y deseas probar la plantilla estándar `hello_world`:

- Nombre de plantilla: `hello_world`
- Idioma: `en_US`
- Variables de la plantilla: **Sin variables**

### Texto libre

El sistema también admite **Texto libre**, pero ese modo debe utilizarse únicamente cuando las reglas de WhatsApp permitan enviar texto dentro de la ventana de conversación vigente. Para avisos masivos iniciados por la organización utiliza una **plantilla aprobada**.

---

## 5. Webhooks y estados de entrega

Los envíos funcionan sin webhooks, pero el sistema solo podrá actualizar automáticamente estados como **entregado** o **fallido** si el proyecto está publicado y los proveedores pueden acceder a una URL HTTPS.

Define:

```env
PUBLIC_BASE_URL=https://tu-dominio.com
```

### Twilio

El sistema genera automáticamente como callback:

```text
https://tu-dominio.com/webhooks/twilio/status/
```

Twilio firma las solicitudes y el proyecto las valida con `TWILIO_AUTH_TOKEN` cuando:

```env
TWILIO_VALIDATE_WEBHOOKS=True
```

También puedes definir una URL manual:

```env
TWILIO_STATUS_CALLBACK_URL=https://tu-dominio.com/webhooks/twilio/status/
```

### Meta WhatsApp

Webhook:

```text
https://tu-dominio.com/webhooks/whatsapp/
```

Configura en Meta:

```env
WHATSAPP_VERIFY_TOKEN=UN_TOKEN_PRIVADO_ELEGIDO_POR_TI
WHATSAPP_APP_SECRET=APP_SECRET_DE_TU_APLICACION_META
```

Usa exactamente el mismo `WHATSAPP_VERIFY_TOKEN` al registrar el webhook en Meta y suscribe el campo de mensajes correspondiente de WhatsApp.

---

## 6. Cómo mandar información a todos los registros

1. Ingresa por **Inicio de sesión administrativo**.
2. Abre **Comunicados masivos**.
3. Pulsa **Agregar comunicado masivo**.
4. En **Destinatarios**:
   - selecciona una hermandad/cofradía para limitar el envío; o
   - déjalo vacío para todas las organizaciones.
5. Marca **Correo**, **SMS** y/o **WhatsApp**.
6. Escribe el asunto y el mensaje.
7. Guarda el comunicado.
8. En la lista, marca el comunicado.
9. En **Acción**, elige **Enviar por los canales seleccionados en el comunicado**.
10. Revisa los resultados y abre **Envíos de comunicados** para ver cada destinatario, canal, proveedor, estado e ID de proveedor.

También existen acciones separadas para enviar únicamente por correo, SMS o WhatsApp.

---

## 7. Personalización de mensajes

Puedes usar los siguientes marcadores tanto en el asunto como en el mensaje:

- `{nombre}` — nombre completo;
- `{primer_nombre}` — primer nombre;
- `{organizacion}` — nombre de la hermandad/cofradía;
- `{tipo_organizacion}` — Hermandad o Cofradía;
- `{asunto}` — asunto del comunicado.

Ejemplo:

```text
Estimado {primer_nombre}:

La {tipo_organizacion} {organizacion} agradece tu participación. Te compartimos la siguiente información...
```

Cada destinatario recibe su propio mensaje personalizado.

---

## 8. Autorización de los devotos

En el formulario de registro aparecen tres autorizaciones independientes:

- correo electrónico;
- SMS;
- WhatsApp.

Ninguna está marcada automáticamente. El devoto decide qué canales permite.

Los registros existentes que antes habían autorizado el consentimiento antiguo de correo conservan únicamente autorización de **correo** después de la migración. **No se habilita SMS ni WhatsApp automáticamente para registros antiguos.**

Un devoto con cuenta puede entrar a **Mi cuenta** y habilitar o deshabilitar los canales para cada inscripción.

---

## 9. Configuración completa de ejemplo

```env
# URL del sistema
PUBLIC_BASE_URL=https://tu-dominio.com
DEFAULT_PHONE_COUNTRY_CODE=+502
MESSAGING_HTTP_TIMEOUT=15

# Correo
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.tu-proveedor.com
EMAIL_PORT=587
EMAIL_HOST_USER=usuario@tu-dominio.com
EMAIL_HOST_PASSWORD=TU_CLAVE
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=TRADICIÓN VIVA <usuario@tu-dominio.com>

# SMS / Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=+1XXXXXXXXXX
TWILIO_MESSAGING_SERVICE_SID=
TWILIO_VALIDATE_WEBHOOKS=True

# WhatsApp / Meta
WHATSAPP_GRAPH_API_VERSION=v25.0
WHATSAPP_ACCESS_TOKEN=TU_ACCESS_TOKEN
WHATSAPP_PHONE_NUMBER_ID=TU_PHONE_NUMBER_ID
WHATSAPP_DEFAULT_TEMPLATE_NAME=tradicion_viva_comunicado
WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE=es
WHATSAPP_VERIFY_TOKEN=TU_TOKEN_DE_VERIFICACION
WHATSAPP_APP_SECRET=TU_APP_SECRET
```

Nunca subas `.env` a GitHub ni compartas los tokens, Auth Tokens, App Secrets o API Keys.

---

## 10. Qué significa “funcional” en esta entrega

La integración y las llamadas reales a Twilio y Meta están implementadas. El proyecto está listo para enviar mensajes cuando se coloquen credenciales válidas de cuentas propias en `.env`.

No es posible incluir credenciales universales dentro del ZIP: Twilio y Meta exigen que cada organización utilice una cuenta, número/remitente y permisos propios. El código no simula envíos; si una credencial falta o el proveedor rechaza un mensaje, el sistema lo registra como **fallido** con el detalle correspondiente.

Los costos, límites, aprobación de remitentes y aprobación de plantillas dependen directamente de Twilio, Meta y del país de destino.
