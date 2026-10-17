# PostgreSQL y pgAdmin

TRADICIÓN VIVA puede seguir usando SQLite en desarrollo. Cuando `.env` tenga `PGDATABASE` o `DATABASE_URL`, Django utilizará PostgreSQL automáticamente.

## 1. Crear la base en PostgreSQL

En pgAdmin crea primero un usuario de aplicación que no sea superusuario y después una base de datos propiedad de ese usuario.

Valores sugeridos:

```text
Base de datos: tradicion_viva
Usuario: tradicion_viva_app
Host: 127.0.0.1
Puerto: 5432
```

Usa una contraseña larga y guárdala únicamente en `.env` o en el gestor de secretos del servidor.

## 2. Configurar Django

Copia `.env.example` como `.env` y completa:

```env
DEBUG=False
PGDATABASE=tradicion_viva
PGUSER=tradicion_viva_app
PGPASSWORD=tu-clave
PGHOST=127.0.0.1
PGPORT=5432
PGSSLMODE=prefer
DATABASE_SSL_REQUIRE=False
```

En producción administrada usa `PGSSLMODE=require` o `DATABASE_URL` con TLS. No subas `.env` al repositorio.

## 3. Crear las tablas

Desde la carpeta del proyecto ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py check --deploy
```

Las migraciones crean las tablas compartidas. Los registros de cada organización se delimitan mediante su relación `hermandad_id`; el administrador de una organización solo debe ver los registros asignados a ella.

La migración `hermandades.0017_rls_organizacion` activa Row-Level Security en `Devoto`, `EventoAgenda`, `TurnoRecorrido`, `Comunicado` y `EnvioComunicado`. Django establece el contexto de la organización en cada petición. `CuentaDevoto` queda fuera porque una misma cuenta puede estar vinculada a varias organizaciones; el acceso del devoto se limita mediante su cuenta y sesión.

La información institucional, imágenes y vídeos públicos no tiene RLS porque debe poder consultarse sin iniciar sesión. Aun así, las operaciones administrativas sobre esos contenidos continúan filtradas por organización desde Django.

Las pruebas reales de RLS corren en `.github/workflows/ci.yml` con PostgreSQL y un rol de prueba sin `BYPASSRLS`; las pruebas ejecutadas solo con SQLite no validan esas políticas.

## Almacenamiento multimedia y respaldos

En desarrollo los archivos multimedia usan `MEDIA_ROOT`. En producción con más de una instancia configura un bucket S3 o compatible y sus credenciales en el gestor de secretos del hosting:

```env
MEDIA_STORAGE_BACKEND=s3
AWS_STORAGE_BUCKET_NAME=nombre-del-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_QUERYSTRING_AUTH=True
AWS_QUERYSTRING_EXPIRE=3600
REDIS_URL=redis://usuario:clave@host:6379/0
MAX_IMAGE_UPLOAD_MB=20
MAX_VIDEO_UPLOAD_MB=250
```

Mantén el bucket privado; habilita versionado o una política de recuperación de objetos y limita las credenciales al bucket de la aplicación. Cada organización recibe una cuota configurable desde Django Admin (2 GB iniciales); imagen, video y audio nuevos se rechazan cuando exceden la cuota. Configura Redis para que el límite de consultas GPS sea compartido entre instancias; sin `REDIS_URL` se usa cache local, apropiada solo para desarrollo o un proceso único.

Activa en el proveedor de PostgreSQL respaldos automáticos diarios, retención mínima de 30 días y cifrado. Habilita versionado/retención para el bucket multimedia y prueba periódicamente la restauración en un entorno separado. Los archivos y la base de datos son respaldos distintos: una copia de PostgreSQL no incluye los objetos del bucket.

## 4. Migrar los datos actuales desde SQLite

Haz una copia del archivo `db.sqlite3` antes de empezar. Con SQLite activo exporta los datos:

```powershell
.\.venv\Scripts\python.exe manage.py dumpdata --natural-foreign --natural-primary --exclude auth.permission --exclude contenttypes --indent 2 > respaldo.json
```

Configura PostgreSQL en `.env`, ejecuta `migrate` y carga el respaldo:

```powershell
.\.venv\Scripts\python.exe manage.py loaddata respaldo.json
```

Revisa especialmente usuarios administrativos, archivos multimedia y registros de comunicaciones antes de eliminar SQLite.

## Verificar RLS desde pgAdmin

En la Query Tool de `tradicion_viva` puedes confirmar que las tablas privadas están protegidas:

```sql
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname IN (
	'hermandades_devoto',
	'hermandades_eventoagenda',
	'hermandades_turnorecorrido',
	'hermandades_comunicado',
	'hermandades_enviocomunicado'
)
ORDER BY relname;
```

Las dos columnas deben aparecer como `true`. No desactives RLS manualmente desde pgAdmin; cualquier cambio debe quedar en una migración revisable.

## Delimitación de seguridad

Esta etapa conserva una única estructura de tablas y aplica aislamiento por organización; no crea una base por organización. Los cambios de esquema y la prueba de RLS deben pasar por CI antes de desplegar. Ejecuta `python manage.py check --deploy` con las variables del entorno real y revisa cada advertencia; activa HSTS en subdominios o preload únicamente si todo el dominio está preparado para HTTPS permanente.