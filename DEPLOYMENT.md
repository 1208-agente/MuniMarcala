# Prueba en línea

Ruta recomendada para una versión editable de la Municipalidad de Marcala:

## Arquitectura

- GitHub: repositorio del código.
- Supabase: base de datos, usuarios y almacenamiento.
- Cloudflare Workers con Static Assets: sitio público y panel editable sin Render.

Cloudflare no ejecuta Flask directamente. La versión web usa `public_build` como assets estáticos y `worker/index.js` para login, administración y formularios públicos.

## Fase 1: prueba pública rápida

Objetivo: mostrar la página a clientes o municipio y habilitar el primer panel editable.

Esta fase usa la carpeta generada `public_build`, el panel `/_panel` y el Worker de Cloudflare. La búsqueda pública funciona con un índice JSON estático.

### Generar la versión pública

```powershell
cd D:\MuniMarcala
python export_static.py
```

La carpeta para subir es:

```text
D:\MuniMarcala\public_build
```

### Probar localmente

```powershell
cd D:\MuniMarcala
python -m http.server 8088 --directory public_build
```

Abrir:

```text
http://127.0.0.1:8088/
```

### Publicar con GitHub + Cloudflare

1. Entrar a Cloudflare.
2. Ir a **Workers & Pages**.
3. Crear aplicación desde un repositorio Git.
4. Seleccionar `1208-agente/MuniMarcala`.
5. Usar `main` como rama de producción.
6. Si pide comando de despliegue, usar:

```text
npx wrangler deploy
```

El archivo raíz `wrangler.jsonc` ya indica que los archivos públicos están en `./public_build`.

### Alcance de esta fase

- `/admin` muestra un panel inicial editable.
- Los cambios del panel se guardan en Supabase.
- La vista pública estática aún no se regenera automáticamente desde Supabase.
- Para actualizar secciones públicas completas todavía se usa `python export_static.py` hasta completar la fase dinámica.

## Fase 2: prueba editable sin Render

Objetivo: que el panel admin funcione en la web.

Esta fase requiere reemplazar las rutas dinámicas de Flask por funciones de Cloudflare. Ver detalles en `ONLINE_EDITING.md`.

1. Crear proyecto en Supabase.
2. Crear base PostgreSQL.
3. Crear bucket público para imágenes y documentos.
4. Usar el Worker incluido para login, administración, cargas y formularios públicos.
5. Configurar Supabase desde `worker/config.js` y `public_build/_panel/config.js`.
6. Ejecutar `supabase_policies.sql` en Supabase.
No se requiere configurar variables en Cloudflare para la prueba actual. La contraseña real será gestionada por Supabase Auth; la tabla interna solo mantiene rol y estado del usuario.

## Fase 3: dominio y seguridad

1. Comprar o configurar dominio.
2. Apuntar DNS en Cloudflare.
3. Activar HTTPS.
4. Configurar reglas de seguridad para `/admin`.
5. Cambiar la contraseña temporal.
6. Crear administrador municipal definitivo y usuarios editores.

## Alternativa temporal

Para enseñar la web desde la computadora local sin desplegar todavía, se puede usar Cloudflare Tunnel. Es útil para demo, pero no es un despliegue final.
