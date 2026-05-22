# Edición en línea con Supabase

Esta configuración convierte el sitio municipal en una aplicación editable en línea:

- Flask sirve el sitio público y el panel admin.
- Supabase PostgreSQL guarda usuarios, publicaciones, trámites, documentos, alcaldes y auditoría.
- Supabase Storage guarda imágenes y PDFs.
- Cloudflare puede manejar dominio, DNS y HTTPS, pero no ejecuta Flask por sí solo.

## 1. Crear Supabase

1. Crear un proyecto en Supabase.
2. Ir a **Project Settings > Database > Connection string**.
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

## 3. Variables de entorno

En el host online configurar:

```text
SECRET_KEY=un_valor_largo_y_seguro
DATABASE_URL=postgresql://...
SUPABASE_URL=https://TU_PROYECTO.supabase.co
SUPABASE_SERVICE_ROLE_KEY=ey...
SUPABASE_BUCKET=municipalidad-marcala
INITIAL_ADMIN_EMAIL=correo@municipalidad.hn
INITIAL_ADMIN_PASSWORD=contraseña_temporal_segura
SESSION_COOKIE_SECURE=1
```

Notas:

- `SUPABASE_SERVICE_ROLE_KEY` es secreto. No debe ir en el navegador ni en GitHub público.
- `INITIAL_ADMIN_PASSWORD` solo se usa para crear el primer admin cuando la base está vacía.
- Después de entrar por primera vez, crear un administrador municipal definitivo y cambiar/pausar el temporal.

## 4. Publicar Flask

Cloudflare Pages no ejecuta esta versión editable porque necesita Python, sesiones, base de datos y subida de archivos.

Usar uno de estos:

- Render
- Railway
- Fly.io

Configuración típica:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
Root directory: municipalidad_marcala
```

Si el repositorio contiene solo `municipalidad_marcala`, el root directory puede quedar vacío.

## 5. Login

Cuando esté desplegado:

```text
https://tu-dominio/admin/login
```

El primer usuario será:

```text
INITIAL_ADMIN_EMAIL
INITIAL_ADMIN_PASSWORD
```

## 6. Cloudflare

Cuando el host Python entregue una URL estable:

1. En Cloudflare, crear un registro `CNAME`.
2. Apuntar `www` o el subdominio elegido al host.
3. Activar proxy naranja si el host lo permite.
4. Mantener HTTPS activo.

## 7. Diferencia con la versión pública rápida

La carpeta `public_build` sirve para demos estáticas.

La versión editable en línea usa:

```text
app.py + PostgreSQL + Supabase Storage
```

Por eso no se regenera con `export_static.py`; se publica como aplicación Flask.
