# Prueba en línea

Ruta recomendada para una versión editable de la Municipalidad de Marcala:

## Arquitectura

- GitHub: repositorio del código.
- Supabase: base de datos PostgreSQL y almacenamiento de imágenes/PDFs.
- Render, Railway o Fly.io: servidor Python/Flask.
- Cloudflare: dominio, DNS, CDN y protección básica.

Cloudflare Pages no es suficiente para esta app completa porque ejecuta sitios estáticos, no una aplicación Flask con login, base de datos y carga de archivos. Sí puede servir una versión estática de demostración pública, pero sin panel de edición.

## Fase 1: prueba pública rápida

Objetivo: mostrar la página a clientes o municipio sin edición en línea.

Esta fase usa la carpeta generada `public_build`. No incluye panel admin en línea. La búsqueda funciona con un índice JSON estático.

### Generar la versión pública

```powershell
cd municipalidad_marcala
python export_static.py
```

La carpeta para subir es:

```text
municipalidad_marcala/public_build
```

### Probar localmente

```powershell
cd municipalidad_marcala
python -m http.server 8088 --directory public_build
```

Abrir:

```text
http://127.0.0.1:8088/
```

### Publicar con GitHub + Cloudflare Pages

1. Crear un repositorio en GitHub.
2. Subir el proyecto o, para la prueba rápida, subir solo el contenido de `public_build`.
3. Entrar a Cloudflare Pages.
4. Crear proyecto conectado al repositorio de GitHub.
5. Configurar:
   - Framework preset: `None`
   - Build command: vacío, si subes `public_build` ya generado.
   - Output directory: `/` si el repositorio contiene solo el contenido de `public_build`.
   - Output directory: `municipalidad_marcala/public_build` si subes todo el proyecto.
6. Publicar.

### Limitaciones de esta fase

- No hay panel de edición en línea.
- Los cambios se hacen localmente en Flask/SQLite y luego se vuelve a ejecutar `python export_static.py`.
- Los PDFs e imágenes quedan como archivos estáticos.
- `/admin` se redirige al inicio en la versión pública.

## Fase 2: prueba editable

Objetivo: que el panel admin funcione en la web.

Esta fase ya está preparada en el código. Ver detalles en `ONLINE_EDITING.md`.

1. Crear proyecto en Supabase.
2. Crear base PostgreSQL.
3. Crear bucket público para imágenes y documentos.
4. Publicar Flask en Render/Railway/Fly.
5. Configurar variables de entorno:

```text
SECRET_KEY=
DATABASE_URL=
AUTH_PROVIDER=supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_BUCKET=
INITIAL_ADMIN_EMAIL=
INITIAL_ADMIN_PASSWORD=
SESSION_COOKIE_SECURE=1
```

Para el primer acceso, crear también ese correo en **Supabase Auth > Users**. La contraseña real será gestionada por Supabase Auth; la tabla interna solo mantiene rol y estado del usuario.

## Fase 3: dominio y seguridad

1. Comprar o configurar dominio.
2. Apuntar DNS en Cloudflare.
3. Activar HTTPS.
4. Configurar reglas de seguridad para `/admin`.
5. Cambiar la contraseña temporal.
6. Crear administrador municipal definitivo y usuarios editores.

## Alternativa temporal

Para enseñar la web desde la computadora local sin desplegar todavía, se puede usar Cloudflare Tunnel. Es útil para demo, pero no es un despliegue final.
