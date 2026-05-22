# Municipalidad de Marcala

Primera versión Flask del sitio institucional de la Municipalidad de Marcala.

## Incluye

- Sitio público con portada, trámites, actualidad, transparencia, agenda, historia y alcaldes.
- Búsqueda global sin distinguir mayúsculas, minúsculas o tildes.
- Panel interno con login por correo y contraseña.
- Roles: administrador y editor.
- Registro de auditoría para crear, editar, entrar y salir.
- Carga de imágenes para portada, publicaciones y biografías.
- Carga de documentos PDF para transparencia.
- Base de datos SQLite local.

## Ejecutar localmente

```powershell
cd municipalidad_marcala
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abrir:

- Sitio público: `http://127.0.0.1:5001/`
- Panel interno: `http://127.0.0.1:5001/admin/login`

El administrador inicial se crea con `INITIAL_ADMIN_EMAIL` y `INITIAL_ADMIN_PASSWORD`.
Para producción, definir ambas variables, cambiar `SECRET_KEY` y crear un administrador municipal definitivo desde el panel.

## Variables recomendadas para producción

```powershell
$env:SECRET_KEY="valor-largo-y-seguro"
$env:INITIAL_ADMIN_EMAIL="correo@municipalidad.gob.hn"
$env:INITIAL_ADMIN_PASSWORD="contraseña-temporal-segura"
$env:SESSION_COOKIE_SECURE="1"
```

## Próximos pasos naturales

- Sustituir fotos temporales por material oficial.
- Crear el administrador municipal definitivo.
- Completar historia oficial, biografías y trámites reales.
- Cargar documentos PDF reales de transparencia.
- Migrar almacenamiento a S3/Supabase Storage cuando se publique en la web.
