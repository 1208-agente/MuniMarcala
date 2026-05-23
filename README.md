# Municipalidad de Marcala

Primera versión Flask del sitio institucional de la Municipalidad de Marcala.

## Incluye

- Sitio público con portada, trámites, actualidad, transparencia, agenda, historia, corporación municipal, alcaldes y contactos.
- Búsqueda global sin distinguir mayúsculas, minúsculas o tildes.
- Panel interno con login por correo y contraseña.
- Roles: administrador y editor.
- Registro de auditoría para crear, editar, entrar y salir.
- Carga de imágenes para portada, publicaciones, biografías y contactos.
- Adjuntos descargables para artículos: PDF, DOCX o imágenes de respaldo.
- Carga de documentos PDF para transparencia.
- Directorio de contactos editable e importable desde CSV, XLS o XLSX.
- Sección pública de denuncias, sugerencias y peticiones con folio, adjuntos y bandeja interna de seguimiento.
- Base de datos SQLite local.

## Ejecutar localmente

```powershell
cd D:\MuniMarcala
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
- Cargar contactos oficiales desde Excel o CSV.
- Cargar miembros reales de la corporación municipal.
- Activar CAPTCHA/Turnstile antes de abrir la sección de participación en internet.
- Publicar la versión editable con GitHub, Supabase PostgreSQL/Auth/Storage y un host Python detrás de Cloudflare.
