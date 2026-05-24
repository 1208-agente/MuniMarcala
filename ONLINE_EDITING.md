# Edición en línea con Supabase

Esta configuración convierte el sitio municipal en una aplicación editable en línea:

- Flask sirve el sitio público y el panel admin en local.
- Supabase Auth valida correos y contraseñas del panel.
- Supabase PostgreSQL guarda perfiles internos, roles, publicaciones, trámites, documentos, alcaldes, contactos, adjuntos y auditoría.
- Supabase Storage guarda imágenes, PDFs, DOCX y respaldos de publicaciones.
- Cloudflare Workers con Static Assets publica la versión web. Cloudflare no ejecuta Flask por sí solo; el Worker reemplaza las rutas dinámicas necesarias para la prueba.

## 1. Crear Supabase

1. Crear un proyecto en Supabase.
2. Usar el botón **Connect** o **Project Settings > Database** para copiar la cadena de conexión si se necesita conectar desde herramientas externas.
3. Copiar la conexión tipo PostgreSQL.
   - Para hosts como Render/Railway, suele convenir el **Session pooler** si el host no soporta IPv6.
   - Supabase documenta que la conexión directa usa `postgresql://...@db.<project>.supabase.co:5432/postgres`, y el pooler usa dominios `pooler.supabase.com`.
   - La app desactiva prepared statements en `psycopg` para evitar problemas con poolers de Supabase.
4. Reemplazar `[YOUR-PASSWORD]` por la contraseña real de la base.

## 2. Crear Storage

1. Ir a **Storage**.
2. Crear un bucket, por ejemplo:

```text
municipalidad-marcala
```

3. Para esta primera demo, hacerlo **public bucket**.
4. Guardar el nombre exacto del bucket para la variable `SUPABASE_BUCKET`.

El sistema sube archivos en estas carpetas del bucket:

```text
images/
documents/
attachments/
```

`attachments/` se usa para respaldos de artículos: PDF, DOCX o imágenes descargables.

## 3. Configuración

La versión Cloudflare queda configurada desde archivos del repositorio, sin variables obligatorias en Cloudflare:

```text
worker/config.js
public_build/_panel/config.js
```

Notas:

- `SUPABASE_URL`, `SUPABASE_ANON_KEY` y `SUPABASE_BUCKET` están en esos archivos.
- No se guarda `SUPABASE_SERVICE_ROLE_KEY` en GitHub.
- La seguridad depende de Supabase Auth + RLS. Ejecutar `supabase_policies.sql` una vez en Supabase.
- El usuario debe existir en **Supabase Auth > Users** y también en la tabla interna `users`.

## 4. Publicar en Cloudflare

Cloudflare no ejecuta esta versión editable Flask porque necesita Python, sesiones, base de datos y subida de archivos.

Sin Render/Railway/Fly, el camino correcto es:

- Publicar primero `public_build` como versión pública rápida.
- Mantener Supabase como fuente de datos y almacenamiento.
- Usar el Worker incluido en `worker/index.js` para las acciones dinámicas:
  - validar sesión contra Supabase Auth
  - leer y guardar contenido en Supabase PostgreSQL
  - subir archivos a Supabase Storage con políticas RLS
  - recibir denuncias, sugerencias y peticiones
  - generar respuestas JSON para el panel admin

GitHub queda como repositorio fuente. Cada `git push` a `main` puede disparar un nuevo despliegue en Cloudflare.

Configuración típica:

```text
Deploy command: npx wrangler deploy
Root directory: vacío
```

El repositorio actual es `1208-agente/MuniMarcala`.

## 5. Login y contraseñas

Cuando esté desplegado:

```text
https://tu-dominio/admin/login
```

Cada usuario del panel debe existir en dos lugares:

1. En **Supabase Auth > Users**, con email y contraseña.
2. En la tabla interna `users`, con ese mismo email y `status='active'`.

Supabase guarda y valida las contraseñas. La tabla interna `users` queda para controlar rol (`admin` o `editor`) y estado (`active`, `paused`, etc.).

## 6. Contactos e importación

El panel tiene una sección **Contactos** para autoridades, empleados, oficinas y puntos de atención.

Puede cargarse contacto por contacto o importar un archivo CSV, XLS o XLSX con columnas como:

```text
nombre, area, cargo, cel, correo, oficina, foto, biografia, estado, etiquetas, orden
```

Notas:

- `estado` puede ser `published`, `draft` o `archived`.
- Si no se indica estado, la importación publica el contacto.
- `foto` puede ser una URL pública o una ruta ya subida, por ejemplo `images/foto.jpg`.
- Si existe el mismo correo o enlace interno, el registro se actualiza.

## 7. Participación ciudadana

El sitio tiene una sección pública:

```text
/participacion
```

Permite recibir:

- Denuncias
- Sugerencias
- Peticiones

El ciudadano puede enviar la solicitud anónima o pedir respuesta dejando nombre, teléfono y/o correo. También puede adjuntar PDF, DOCX o imágenes como respaldo.

La solicitud no se publica en el sitio. Solo se revisa desde:

```text
/admin/participacion
```

Estados internos:

```text
nuevo
en_tramite
resuelto
irrelevante
```

Recomendación para producción:

- Mantener estos registros en base de datos, sin borrado desde el panel.
- Agregar CAPTCHA o Turnstile de Cloudflare antes de abrirlo al público para reducir spam.
- Limitar tamaño de adjuntos y revisar permisos del bucket de Supabase Storage.
- Crear un rol/editor municipal responsable de revisar esta bandeja.

## 8. Cloudflare

Cuando el host Python entregue una URL estable:

1. En Cloudflare, crear un registro `CNAME`.
2. Apuntar `www` o el subdominio elegido al host.
3. Activar proxy naranja si el host lo permite.
4. Mantener HTTPS activo.

## 9. Diferencia con la versión pública rápida

La carpeta `public_build` sirve para demos estáticas.

La versión editable en línea usa:

```text
app.py + PostgreSQL + Supabase Storage
```

Por eso no se regenera con `export_static.py`; se publica como aplicación Flask.
