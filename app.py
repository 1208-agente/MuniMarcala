from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # Local SQLite mode does not require psycopg.
    psycopg = None
    dict_row = None

try:
    from supabase import create_client
except ImportError:  # Supabase Storage is optional in local mode.
    create_client = None


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "uploads"))
DB_PATH = DATA_DIR / "municipalidad_marcala.sqlite3"
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
USE_POSTGRES = bool(DATABASE_URL)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "")
USE_SUPABASE_STORAGE = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_BUCKET)
SUPABASE_STORAGE_CLIENT = None

SITE_NAME = os.environ.get("SITE_NAME", "Municipalidad de Marcala")
INITIAL_ADMIN_EMAIL = os.environ.get("INITIAL_ADMIN_EMAIL", "1208agente@gmail.com")
INITIAL_ADMIN_PASSWORD = os.environ.get("INITIAL_ADMIN_PASSWORD", "change-me-local")
ALLOWED_IMAGES = {"jpg", "jpeg", "png", "webp"}
ALLOWED_DOCUMENTS = {"pdf"}

CONTENT_CATEGORIES = [
    ("noticias", "Noticias"),
    ("comunicados", "Comunicados"),
    ("avisos", "Avisos"),
    ("obras-y-proyectos", "Obras y proyectos"),
    ("campanas", "Campañas públicas"),
]

DOCUMENT_CATEGORIES = [
    ("presupuesto", "Presupuesto"),
    ("rendicion-de-cuentas", "Rendición de cuentas"),
    ("actas", "Actas"),
    ("licitaciones", "Licitaciones"),
    ("compras", "Compras"),
    ("ordenanzas", "Ordenanzas"),
    ("informes", "Informes"),
    ("otros", "Otros"),
]

STATUSES = [
    ("published", "Publicado"),
    ("draft", "Borrador"),
    ("archived", "Archivado"),
]


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / "images").mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / "documents").mkdir(parents=True, exist_ok=True)
    init_db()

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        return {
            "site_name": get_setting("site_name", SITE_NAME),
            "current_user": current_user(),
            "content_categories": CONTENT_CATEGORIES,
            "document_categories": DOCUMENT_CATEGORIES,
            "statuses": STATUSES,
            "trending_tags": trending_tags(),
            "asset_url": asset_url,
            "split_tags": split_tags,
            "now": datetime.now(UTC),
        }

    @app.template_filter("date_label")
    def date_label(value: str | None) -> str:
        if not value:
            return ""
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            return value

    @app.template_filter("category_label")
    def category_label(value: str) -> str:
        choices = dict(CONTENT_CATEGORIES + DOCUMENT_CATEGORIES)
        return choices.get(value, value.replace("-", " ").title())

    @app.template_filter("status_label")
    def status_label(value: str) -> str:
        return dict(STATUSES).get(value, value)

    @app.get("/")
    def home():
        featured = query_all(
            """
            SELECT * FROM content
            WHERE status = 'published'
            ORDER BY COALESCE(published_at, created_at) DESC
            LIMIT 6
            """
        )
        services = query_all(
            "SELECT * FROM services WHERE status = 'published' ORDER BY title LIMIT 6"
        )
        docs = query_all(
            """
            SELECT * FROM documents
            WHERE status = 'published'
            ORDER BY COALESCE(document_date, created_at) DESC
            LIMIT 4
            """
        )
        current_mayor = query_one(
            "SELECT * FROM mayors WHERE is_current = 1 AND status = 'published' LIMIT 1"
        )
        return render_template(
            "home.html",
            featured=featured,
            services=services,
            docs=docs,
            current_mayor=current_mayor,
            hero_image=get_setting("hero_image", "images/hero-marcala.jpg"),
            hero_title=get_setting("hero_title", "Marcala avanza con su gente"),
            hero_summary=get_setting(
                "hero_summary",
                "Información municipal, trámites, actualidad, transparencia y servicios para la ciudadanía.",
            ),
        )

    @app.get("/actualidad")
    def actualidad():
        category = request.args.get("categoria", "todos")
        params: list[Any] = []
        where = "status = 'published'"
        if category != "todos":
            where += " AND category = ?"
            params.append(category)
        items = query_all(
            f"""
            SELECT * FROM content
            WHERE {where}
            ORDER BY COALESCE(published_at, created_at) DESC
            """,
            params,
        )
        return render_template("content_list.html", items=items, selected_category=category)

    @app.get("/actualidad/<slug>")
    def actualidad_detail(slug: str):
        item = query_one("SELECT * FROM content WHERE slug = ? AND status = 'published'", [slug])
        if not item:
            abort(404)
        return render_template("content_detail.html", item=item)

    @app.get("/admin/<kind>/<int:record_id>/vista")
    @login_required
    def admin_content_preview(kind: str, record_id: int):
        if kind not in {"actualidad", "agenda"}:
            abort(404)
        item = query_one("SELECT * FROM content WHERE id = ? AND kind = ?", [record_id, kind])
        if not item:
            abort(404)
        return render_template("content_detail.html", item=item, admin_preview=True)

    @app.get("/tramites")
    def tramites():
        items = query_all("SELECT * FROM services WHERE status = 'published' ORDER BY title")
        return render_template("services.html", items=items)

    @app.get("/tramites/<slug>")
    def tramite_detail(slug: str):
        item = query_one("SELECT * FROM services WHERE slug = ? AND status = 'published'", [slug])
        if not item:
            abort(404)
        return render_template("service_detail.html", item=item)

    @app.get("/transparencia")
    def transparencia():
        category = request.args.get("categoria", "todos")
        params: list[Any] = []
        where = "status = 'published'"
        if category != "todos":
            where += " AND category = ?"
            params.append(category)
        items = query_all(
            f"""
            SELECT * FROM documents
            WHERE {where}
            ORDER BY year DESC, COALESCE(document_date, created_at) DESC
            """,
            params,
        )
        return render_template("documents.html", items=items, selected_category=category)

    @app.get("/transparencia/<slug>")
    def document_detail(slug: str):
        item = query_one("SELECT * FROM documents WHERE slug = ? AND status = 'published'", [slug])
        if not item:
            abort(404)
        return render_template("document_detail.html", item=item)

    @app.get("/municipalidad")
    def municipalidad():
        current_mayor = query_one(
            "SELECT * FROM mayors WHERE is_current = 1 AND status = 'published' LIMIT 1"
        )
        former_mayors = query_all(
            """
            SELECT * FROM mayors
            WHERE status = 'published' AND is_current = 0
            ORDER BY period_start DESC
            """
        )
        return render_template(
            "municipality.html",
            history_title=get_setting("history_title", "Historia de Marcala"),
            history_body=get_setting("history_body", sample_history()),
            current_mayor=current_mayor,
            former_mayors=former_mayors,
        )

    @app.get("/municipalidad/alcaldes/<slug>")
    def mayor_detail(slug: str):
        item = query_one("SELECT * FROM mayors WHERE slug = ? AND status = 'published'", [slug])
        if not item:
            abort(404)
        return render_template("mayor_detail.html", item=item)

    @app.get("/agenda")
    def agenda():
        items = query_all(
            """
            SELECT * FROM content
            WHERE status = 'published' AND kind = 'agenda'
            ORDER BY COALESCE(event_date, published_at, created_at)
            """
        )
        return render_template("agenda.html", items=items)

    @app.get("/buscar")
    def buscar():
        q = request.args.get("q", "").strip()
        tag = request.args.get("tag", "").strip()
        results = search_records(q, tag)
        return render_template("search.html", query=q, tag=tag, results=results)

    @app.get("/privacidad")
    def privacidad():
        return render_template("privacy.html")

    @app.get("/uploads/<path:filename>")
    def uploads(filename: str):
        return send_from_directory(UPLOAD_DIR, filename)

    @app.get("/admin/login")
    def admin_login():
        return render_template("admin_login.html")

    @app.post("/admin/login")
    def admin_login_post():
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE email = ? AND status = 'active'", [email])
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Correo o contraseña incorrectos.", "error")
            return redirect(url_for("admin_login"))
        session.clear()
        session["user_id"] = user["id"]
        audit("login", "users", user["id"], user["name"])
        return redirect(url_for("admin_home"))

    @app.get("/admin/logout")
    def admin_logout():
        if current_user():
            audit("logout", "users", current_user()["id"], current_user()["name"])
        session.clear()
        return redirect(url_for("admin_login"))

    @app.get("/admin")
    @login_required
    def admin_home():
        sections = [
            {
                "id": "actualidad",
                "label": "Actualidad",
                "description": "Noticias, comunicados, avisos y obras.",
                "count": query_value("SELECT COUNT(*) FROM content WHERE kind = 'actualidad'"),
                "records": query_all("SELECT * FROM content WHERE kind = 'actualidad' ORDER BY updated_at DESC, created_at DESC LIMIT 6"),
                "new_url": url_for("admin_content_new", kind="actualidad"),
                "edit_base": "/admin/actualidad",
                "title_field": "title",
                "meta_field": "category",
            },
            {
                "id": "agenda",
                "label": "Agenda",
                "description": "Actividades y fechas públicas.",
                "count": query_value("SELECT COUNT(*) FROM content WHERE kind = 'agenda'"),
                "records": query_all("SELECT * FROM content WHERE kind = 'agenda' ORDER BY event_date DESC, updated_at DESC LIMIT 6"),
                "new_url": url_for("admin_content_new", kind="agenda"),
                "edit_base": "/admin/agenda",
                "title_field": "title",
                "meta_field": "event_date",
            },
            {
                "id": "tramites",
                "label": "Trámites",
                "description": "Requisitos, pasos y dependencias.",
                "count": query_value("SELECT COUNT(*) FROM services"),
                "records": query_all("SELECT * FROM services ORDER BY updated_at DESC, created_at DESC LIMIT 6"),
                "new_url": url_for("admin_service_new"),
                "edit_base": "/admin/tramites",
                "title_field": "title",
                "meta_field": "department",
            },
            {
                "id": "documentos",
                "label": "Transparencia",
                "description": "PDFs, informes, presupuesto y actas.",
                "count": query_value("SELECT COUNT(*) FROM documents"),
                "records": query_all("SELECT * FROM documents ORDER BY updated_at DESC, created_at DESC LIMIT 6"),
                "new_url": url_for("admin_document_new"),
                "edit_base": "/admin/documentos",
                "title_field": "title",
                "meta_field": "category",
            },
            {
                "id": "alcaldes",
                "label": "Alcaldes",
                "description": "Biografías e historia institucional.",
                "count": query_value("SELECT COUNT(*) FROM mayors"),
                "records": query_all("SELECT * FROM mayors ORDER BY is_current DESC, period_start DESC LIMIT 6"),
                "new_url": url_for("admin_mayor_new"),
                "edit_base": "/admin/alcaldes",
                "title_field": "name",
                "meta_field": "period_start",
            },
        ]
        return render_template("admin_home.html", sections=sections)

    @app.get("/admin/actualidad")
    @login_required
    def admin_content():
        items = query_all(
            "SELECT * FROM content WHERE kind = 'actualidad' ORDER BY updated_at DESC, created_at DESC"
        )
        return render_template("admin_content_list.html", items=items, kind="actualidad")

    @app.get("/admin/agenda")
    @login_required
    def admin_agenda():
        items = query_all("SELECT * FROM content WHERE kind = 'agenda' ORDER BY event_date DESC")
        return render_template("admin_content_list.html", items=items, kind="agenda")

    @app.route("/admin/<kind>/nuevo", methods=["GET", "POST"])
    @login_required
    def admin_content_new(kind: str):
        if kind not in {"actualidad", "agenda"}:
            abort(404)
        if request.method == "POST":
            record_id = save_content(kind)
            flash("Contenido creado.", "success")
            return redirect_after_content_save(kind, record_id)
        return render_template("admin_content_form.html", item=None, kind=kind)

    @app.route("/admin/<kind>/<int:record_id>", methods=["GET", "POST"])
    @login_required
    def admin_content_edit(kind: str, record_id: int):
        if kind not in {"actualidad", "agenda"}:
            abort(404)
        item = query_one("SELECT * FROM content WHERE id = ? AND kind = ?", [record_id, kind])
        if not item:
            abort(404)
        if request.method == "POST":
            save_content(kind, item)
            flash("Contenido actualizado.", "success")
            return redirect_after_content_save(kind, record_id)
        return render_template("admin_content_form.html", item=item, kind=kind)

    @app.get("/admin/<kind>/<int:record_id>/guardado")
    @login_required
    def admin_content_saved(kind: str, record_id: int):
        if kind not in {"actualidad", "agenda"}:
            abort(404)
        item = query_one("SELECT * FROM content WHERE id = ? AND kind = ?", [record_id, kind])
        if not item:
            abort(404)
        public_url = url_for("actualidad_detail", slug=item["slug"]) if item["status"] == "published" else ""
        return render_template("admin_content_saved.html", item=item, kind=kind, public_url=public_url)

    @app.get("/admin/tramites")
    @login_required
    def admin_services():
        items = query_all("SELECT * FROM services ORDER BY updated_at DESC, created_at DESC")
        return render_template("admin_services_list.html", items=items)

    @app.route("/admin/tramites/nuevo", methods=["GET", "POST"])
    @login_required
    def admin_service_new():
        if request.method == "POST":
            record_id = save_service()
            flash("Trámite creado.", "success")
            return redirect(url_for("admin_service_edit", record_id=record_id))
        return render_template("admin_service_form.html", item=None)

    @app.route("/admin/tramites/<int:record_id>", methods=["GET", "POST"])
    @login_required
    def admin_service_edit(record_id: int):
        item = query_one("SELECT * FROM services WHERE id = ?", [record_id])
        if not item:
            abort(404)
        if request.method == "POST":
            save_service(item)
            flash("Trámite actualizado.", "success")
            return redirect(url_for("admin_service_edit", record_id=record_id))
        return render_template("admin_service_form.html", item=item)

    @app.get("/admin/documentos")
    @login_required
    def admin_documents():
        items = query_all("SELECT * FROM documents ORDER BY year DESC, updated_at DESC")
        return render_template("admin_documents_list.html", items=items)

    @app.route("/admin/documentos/nuevo", methods=["GET", "POST"])
    @login_required
    def admin_document_new():
        if request.method == "POST":
            record_id = save_document()
            flash("Documento creado.", "success")
            return redirect(url_for("admin_document_edit", record_id=record_id))
        return render_template("admin_document_form.html", item=None)

    @app.route("/admin/documentos/<int:record_id>", methods=["GET", "POST"])
    @login_required
    def admin_document_edit(record_id: int):
        item = query_one("SELECT * FROM documents WHERE id = ?", [record_id])
        if not item:
            abort(404)
        if request.method == "POST":
            save_document(item)
            flash("Documento actualizado.", "success")
            return redirect(url_for("admin_document_edit", record_id=record_id))
        return render_template("admin_document_form.html", item=item)

    @app.get("/admin/alcaldes")
    @login_required
    def admin_mayors():
        items = query_all("SELECT * FROM mayors ORDER BY is_current DESC, period_start DESC")
        return render_template("admin_mayors_list.html", items=items)

    @app.route("/admin/alcaldes/nuevo", methods=["GET", "POST"])
    @login_required
    def admin_mayor_new():
        if request.method == "POST":
            record_id = save_mayor()
            flash("Biografía creada.", "success")
            return redirect(url_for("admin_mayor_edit", record_id=record_id))
        return render_template("admin_mayor_form.html", item=None)

    @app.route("/admin/alcaldes/<int:record_id>", methods=["GET", "POST"])
    @login_required
    def admin_mayor_edit(record_id: int):
        item = query_one("SELECT * FROM mayors WHERE id = ?", [record_id])
        if not item:
            abort(404)
        if request.method == "POST":
            save_mayor(item)
            flash("Biografía actualizada.", "success")
            return redirect(url_for("admin_mayor_edit", record_id=record_id))
        return render_template("admin_mayor_form.html", item=item)

    @app.get("/admin/usuarios")
    @admin_required
    def admin_users():
        items = query_all("SELECT * FROM users ORDER BY role, name")
        return render_template("admin_users_list.html", items=items)

    @app.route("/admin/usuarios/nuevo", methods=["GET", "POST"])
    @admin_required
    def admin_user_new():
        if request.method == "POST":
            record_id = save_user()
            flash("Usuario creado.", "success")
            return redirect(url_for("admin_users"))
        return render_template("admin_user_form.html", item=None)

    @app.route("/admin/usuarios/<int:record_id>", methods=["GET", "POST"])
    @admin_required
    def admin_user_edit(record_id: int):
        item = query_one("SELECT * FROM users WHERE id = ?", [record_id])
        if not item:
            abort(404)
        if request.method == "POST":
            save_user(item)
            flash("Usuario actualizado.", "success")
            return redirect(url_for("admin_users"))
        return render_template("admin_user_form.html", item=item)

    @app.route("/admin/configuracion", methods=["GET", "POST"])
    @admin_required
    def admin_settings():
        keys = [
            "site_name",
            "hero_title",
            "hero_summary",
            "history_title",
            "history_body",
            "contact_phone",
            "contact_email",
            "contact_address",
        ]
        if request.method == "POST":
            before = {key: get_setting(key, "") for key in keys}
            for key in keys:
                set_setting(key, request.form.get(key, "").strip())
            hero_file = request.files.get("hero_image_file")
            if hero_file and hero_file.filename:
                set_setting("hero_image", save_upload(hero_file, "images", ALLOWED_IMAGES))
            audit("update", "settings", 0, "Configuración", changed_fields(before, {key: get_setting(key, "") for key in keys}))
            flash("Configuración actualizada.", "success")
            return redirect(url_for("admin_settings"))
        settings = {key: get_setting(key, "") for key in keys}
        settings["hero_image"] = get_setting("hero_image", "images/hero-marcala.jpg")
        return render_template("admin_settings.html", settings=settings)

    @app.get("/admin/auditoria")
    @admin_required
    def admin_audit():
        items = query_all("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 200")
        return render_template("admin_audit.html", items=items)

    return app


def get_db() -> Any:
    if USE_POSTGRES:
        if psycopg is None or dict_row is None:
            raise RuntimeError("DATABASE_URL está configurado, pero falta instalar psycopg.")
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    if USE_POSTGRES:
        with get_db() as db:
            for statement in postgres_schema():
                db.execute(statement)
            db.commit()
    else:
        with get_db() as db:
            db.executescript(sqlite_schema())
    seed_data()


def sqlite_schema() -> str:
    return """
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'editor',
      status TEXT NOT NULL DEFAULT 'active',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS content (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT NOT NULL DEFAULT 'actualidad',
      title TEXT NOT NULL,
      slug TEXT NOT NULL UNIQUE,
      category TEXT NOT NULL DEFAULT 'noticias',
      summary TEXT,
      body TEXT,
      image_path TEXT,
      image_alt TEXT,
      published_at TEXT,
      event_date TEXT,
      status TEXT NOT NULL DEFAULT 'draft',
      tags TEXT,
      cta_label TEXT,
      cta_url TEXT,
      created_by INTEGER,
      updated_by INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS services (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      slug TEXT NOT NULL UNIQUE,
      department TEXT,
      summary TEXT,
      requirements TEXT,
      steps TEXT,
      cost TEXT,
      estimated_time TEXT,
      schedule TEXT,
      location TEXT,
      contact TEXT,
      document_url TEXT,
      status TEXT NOT NULL DEFAULT 'draft',
      tags TEXT,
      created_by INTEGER,
      updated_by INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS documents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      slug TEXT NOT NULL UNIQUE,
      category TEXT NOT NULL DEFAULT 'otros',
      description TEXT,
      document_date TEXT,
      year INTEGER,
      department TEXT,
      file_path TEXT,
      external_url TEXT,
      status TEXT NOT NULL DEFAULT 'draft',
      tags TEXT,
      created_by INTEGER,
      updated_by INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS mayors (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      slug TEXT NOT NULL UNIQUE,
      period_start TEXT,
      period_end TEXT,
      biography TEXT,
      photo_path TEXT,
      is_current INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'draft',
      tags TEXT,
      created_by INTEGER,
      updated_by INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      user_email TEXT,
      action TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id INTEGER,
      entity_title TEXT,
      details TEXT,
      ip TEXT,
      user_agent TEXT,
      created_at TEXT NOT NULL
    );
    """


def postgres_schema() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'editor',
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS content (
          id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          kind TEXT NOT NULL DEFAULT 'actualidad',
          title TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          category TEXT NOT NULL DEFAULT 'noticias',
          summary TEXT,
          body TEXT,
          image_path TEXT,
          image_alt TEXT,
          published_at TEXT,
          event_date TEXT,
          status TEXT NOT NULL DEFAULT 'draft',
          tags TEXT,
          cta_label TEXT,
          cta_url TEXT,
          created_by INTEGER,
          updated_by INTEGER,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS services (
          id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          title TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          department TEXT,
          summary TEXT,
          requirements TEXT,
          steps TEXT,
          cost TEXT,
          estimated_time TEXT,
          schedule TEXT,
          location TEXT,
          contact TEXT,
          document_url TEXT,
          status TEXT NOT NULL DEFAULT 'draft',
          tags TEXT,
          created_by INTEGER,
          updated_by INTEGER,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          title TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          category TEXT NOT NULL DEFAULT 'otros',
          description TEXT,
          document_date TEXT,
          year INTEGER,
          department TEXT,
          file_path TEXT,
          external_url TEXT,
          status TEXT NOT NULL DEFAULT 'draft',
          tags TEXT,
          created_by INTEGER,
          updated_by INTEGER,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mayors (
          id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          name TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          period_start TEXT,
          period_end TEXT,
          biography TEXT,
          photo_path TEXT,
          is_current INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'draft',
          tags TEXT,
          created_by INTEGER,
          updated_by INTEGER,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          user_id INTEGER,
          user_email TEXT,
          action TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id INTEGER,
          entity_title TEXT,
          details TEXT,
          ip TEXT,
          user_agent TEXT,
          created_at TEXT NOT NULL
        )
        """,
    ]


def seed_data() -> None:
    now = utc_now()
    if not query_one("SELECT id FROM users LIMIT 1"):
        execute(
            """
            INSERT INTO users (name, email, password_hash, role, status, created_at, updated_at)
            VALUES (?, ?, ?, 'admin', 'active', ?, ?)
            """,
            [
                "Administrador inicial",
                INITIAL_ADMIN_EMAIL.lower(),
                generate_password_hash(INITIAL_ADMIN_PASSWORD),
                now,
                now,
            ],
        )
    defaults = {
        "site_name": SITE_NAME,
        "hero_title": "Marcala avanza con su gente",
        "hero_summary": "Información municipal, trámites, actualidad, transparencia y servicios para la ciudadanía.",
        "hero_image": "images/hero-marcala.jpg",
        "history_title": "Historia de Marcala",
        "history_body": sample_history(),
        "contact_phone": "+504 0000-0000",
        "contact_email": "info@municipalidadmarcala.hn",
        "contact_address": "Marcala, La Paz, Honduras",
    }
    for key, value in defaults.items():
        execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", [key, value])

    if not query_one("SELECT id FROM content LIMIT 1"):
        seed_content(now)
    if not query_one("SELECT id FROM services LIMIT 1"):
        seed_services(now)
    if not query_one("SELECT id FROM mayors LIMIT 1"):
        execute(
            """
            INSERT INTO mayors
            (name, slug, period_start, period_end, biography, photo_path, is_current, status, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'published', ?, ?, ?)
            """,
            [
                "Autoridad municipal actual",
                "autoridad-municipal-actual",
                "2026",
                "",
                "Biografía editable de la persona que actualmente dirige la Municipalidad de Marcala. Este espacio puede incluir trayectoria, prioridades de gestión y una fotografía oficial.",
                "images/mayor-placeholder.jpg",
                "municipalidad, gestion",
                now,
                now,
            ],
        )
    if not query_one("SELECT id FROM documents LIMIT 1"):
        execute(
            """
            INSERT INTO documents
            (title, slug, category, description, document_date, year, department, status, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'published', ?, ?, ?)
            """,
            [
                "Ejemplo de documento de transparencia",
                "ejemplo-documento-transparencia",
                "informes",
                "Ficha de muestra para reemplazar por un PDF oficial cuando el municipio cargue sus documentos.",
                "2026-01-15",
                2026,
                "Secretaría Municipal",
                "transparencia, informe",
                now,
                now,
            ],
        )


def seed_content(now: str) -> None:
    samples = [
        (
            "actualidad",
            "Inicio de mejoras en calles urbanas",
            "obras-y-proyectos",
            "La Municipalidad presenta una intervención de mantenimiento vial en barrios priorizados.",
            "Este contenido de muestra puede reemplazarse por una publicación oficial con fotografías, avances, responsables y fechas relevantes del proyecto.",
            "images/news-street-work.jpg",
            "2026-05-01",
            "",
            "obras, infraestructura, barrios",
        ),
        (
            "actualidad",
            "Campaña municipal de limpieza",
            "avisos",
            "Aviso ciudadano sobre jornada de limpieza y ornato.",
            "La publicación puede incluir horarios, puntos de encuentro, recomendaciones y dependencias encargadas.",
            "images/news-community.jpg",
            "2026-05-05",
            "",
            "ambiente, comunidad",
        ),
        (
            "agenda",
            "Sesión informativa comunitaria",
            "comunicados",
            "Actividad de agenda pública para informar a vecinos sobre servicios municipales.",
            "Los eventos de agenda pueden reutilizarse editando la fecha, el texto y la imagen.",
            "images/news-town-hall.jpg",
            "2026-05-12",
            "2026-06-15",
            "agenda, comunidad",
        ),
    ]
    for kind, title, category, summary, body, image, published, event_date, tags in samples:
        execute(
            """
            INSERT INTO content
            (kind, title, slug, category, summary, body, image_path, published_at, event_date, status, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', ?, ?, ?)
            """,
            [kind, title, unique_slug(title, "content"), category, summary, body, image, published, event_date, tags, now, now],
        )


def seed_services(now: str) -> None:
    samples = [
        (
            "Solicitud de constancia municipal",
            "Secretaría Municipal",
            "Información para solicitar constancias emitidas por la Municipalidad.",
            "Documento de identidad vigente\nDatos exactos que deben constar en la certificación\nComprobante de pago si aplica",
            "Presentarse en Secretaría Municipal\nIndicar el tipo de constancia requerida\nRealizar pago de tasa si corresponde\nRetirar el documento en el plazo indicado",
            "Según tasa municipal vigente",
            "1 a 3 días hábiles",
            "lunes a viernes, horario administrativo",
            "Edificio municipal",
            "Secretaría Municipal",
            "tramites, constancias",
        ),
        (
            "Pago de tasas municipales",
            "Tesorería Municipal",
            "Pasos para consultar y pagar tasas o servicios municipales.",
            "Identificación del contribuyente\nClave catastral o referencia del servicio cuando aplique",
            "Solicitar estado de cuenta\nVerificar monto pendiente\nRealizar pago en Tesorería\nConservar recibo oficial",
            "Variable según servicio",
            "Atención inmediata",
            "lunes a viernes, horario administrativo",
            "Tesorería Municipal",
            "Tesorería Municipal",
            "pagos, tesoreria",
        ),
    ]
    for title, department, summary, requirements, steps, cost, estimated, schedule, location, contact, tags in samples:
        execute(
            """
            INSERT INTO services
            (title, slug, department, summary, requirements, steps, cost, estimated_time, schedule, location, contact, status, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', ?, ?, ?)
            """,
            [title, unique_slug(title, "services"), department, summary, requirements, steps, cost, estimated, schedule, location, contact, tags, now, now],
        )


def prepare_sql(sql: str) -> str:
    if not USE_POSTGRES:
        return sql
    sql = sql.replace(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO NOTHING",
    )
    return sql.replace("?", "%s")


def sql_returns_id(sql: str) -> bool:
    return bool(
        re.match(
            r"^\s*INSERT\s+INTO\s+(users|content|services|documents|mayors|audit_logs)\b",
            sql,
            flags=re.IGNORECASE,
        )
    )


def query_all(sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[Any]:
    sql = prepare_sql(sql)
    with get_db() as db:
        cursor = db.execute(sql, params)
        return cursor.fetchall()


def query_one(sql: str, params: list[Any] | tuple[Any, ...] = ()) -> Any | None:
    sql = prepare_sql(sql)
    with get_db() as db:
        cursor = db.execute(sql, params)
        return cursor.fetchone()


def query_value(sql: str, params: list[Any] | tuple[Any, ...] = ()) -> Any:
    row = query_one(sql, params)
    if not row:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def execute(sql: str, params: list[Any] | tuple[Any, ...] = ()) -> int:
    sql = prepare_sql(sql)
    with get_db() as db:
        if USE_POSTGRES and sql_returns_id(sql) and " RETURNING " not in sql.upper():
            sql = f"{sql.rstrip()} RETURNING id"
        cursor = db.execute(sql, params)
        row = cursor.fetchone() if USE_POSTGRES and " RETURNING " in sql.upper() else None
        db.commit()
        if row:
            return int(row["id"] if isinstance(row, dict) else row[0])
        if hasattr(cursor, "lastrowid") and cursor.lastrowid:
            return int(cursor.lastrowid)
        return 0


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def current_user() -> sqlite3.Row | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_one("SELECT * FROM users WHERE id = ? AND status = 'active'", [user_id])


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not current_user():
            if request.method == "POST":
                flash("Tu sesión venció antes de guardar. Inicia sesión y vuelve a guardar los cambios.", "error")
            else:
                flash("Inicia sesión para continuar.", "error")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not user:
            return redirect(url_for("admin_login"))
        if user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def redirect_after_content_save(kind: str, record_id: int) -> Any:
    action = request.form.get("action", "save")
    if action == "save_preview":
        return redirect(url_for("admin_content_preview", kind=kind, record_id=record_id))
    return redirect(url_for("admin_content_edit", kind=kind, record_id=record_id))


def get_setting(key: str, default: str = "") -> str:
    row = query_one("SELECT value FROM settings WHERE key = ?", [key])
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        [key, value],
    )


def save_content(kind: str, item: sqlite3.Row | None = None) -> int:
    now = utc_now()
    user = current_user()
    title = request.form.get("title", "").strip()
    slug = request.form.get("slug", "").strip() or title
    image_path = item["image_path"] if item else ""
    file = request.files.get("image_file")
    if file and file.filename:
        image_path = save_upload(file, "images", ALLOWED_IMAGES)
    values = {
        "kind": kind,
        "title": title,
        "slug": unique_slug(slug, "content", item["id"] if item else None),
        "category": request.form.get("category", "noticias"),
        "summary": request.form.get("summary", "").strip(),
        "body": request.form.get("body", "").strip(),
        "image_path": image_path,
        "image_alt": request.form.get("image_alt", "").strip(),
        "published_at": request.form.get("published_at", "").strip(),
        "event_date": request.form.get("event_date", "").strip(),
        "status": request.form.get("status", "draft"),
        "tags": clean_tags(request.form.get("tags", "")),
        "cta_label": request.form.get("cta_label", "").strip(),
        "cta_url": request.form.get("cta_url", "").strip(),
        "updated_by": user["id"] if user else None,
        "updated_at": now,
    }
    if item:
        before = dict(item)
        execute(
            """
            UPDATE content SET kind=?, title=?, slug=?, category=?, summary=?, body=?, image_path=?,
            image_alt=?, published_at=?, event_date=?, status=?, tags=?, cta_label=?, cta_url=?,
            updated_by=?, updated_at=? WHERE id=?
            """,
            list(values.values()) + [item["id"]],
        )
        audit("update", "content", item["id"], title, changed_fields(before, values))
        return int(item["id"])
    record_id = execute(
        """
        INSERT INTO content
        (kind, title, slug, category, summary, body, image_path, image_alt, published_at, event_date,
        status, tags, cta_label, cta_url, created_by, updated_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            values["kind"],
            values["title"],
            values["slug"],
            values["category"],
            values["summary"],
            values["body"],
            values["image_path"],
            values["image_alt"],
            values["published_at"],
            values["event_date"],
            values["status"],
            values["tags"],
            values["cta_label"],
            values["cta_url"],
            user["id"] if user else None,
            user["id"] if user else None,
            now,
            now,
        ],
    )
    audit("create", "content", record_id, title)
    return record_id


def save_service(item: sqlite3.Row | None = None) -> int:
    now = utc_now()
    user = current_user()
    title = request.form.get("title", "").strip()
    values = {
        "title": title,
        "slug": unique_slug(request.form.get("slug", "").strip() or title, "services", item["id"] if item else None),
        "department": request.form.get("department", "").strip(),
        "summary": request.form.get("summary", "").strip(),
        "requirements": request.form.get("requirements", "").strip(),
        "steps": request.form.get("steps", "").strip(),
        "cost": request.form.get("cost", "").strip(),
        "estimated_time": request.form.get("estimated_time", "").strip(),
        "schedule": request.form.get("schedule", "").strip(),
        "location": request.form.get("location", "").strip(),
        "contact": request.form.get("contact", "").strip(),
        "document_url": request.form.get("document_url", "").strip(),
        "status": request.form.get("status", "draft"),
        "tags": clean_tags(request.form.get("tags", "")),
        "updated_by": user["id"] if user else None,
        "updated_at": now,
    }
    if item:
        before = dict(item)
        execute(
            """
            UPDATE services SET title=?, slug=?, department=?, summary=?, requirements=?, steps=?,
            cost=?, estimated_time=?, schedule=?, location=?, contact=?, document_url=?, status=?,
            tags=?, updated_by=?, updated_at=? WHERE id=?
            """,
            list(values.values()) + [item["id"]],
        )
        audit("update", "services", item["id"], title, changed_fields(before, values))
        return int(item["id"])
    record_id = execute(
        """
        INSERT INTO services
        (title, slug, department, summary, requirements, steps, cost, estimated_time, schedule,
        location, contact, document_url, status, tags, created_by, updated_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            values["title"],
            values["slug"],
            values["department"],
            values["summary"],
            values["requirements"],
            values["steps"],
            values["cost"],
            values["estimated_time"],
            values["schedule"],
            values["location"],
            values["contact"],
            values["document_url"],
            values["status"],
            values["tags"],
            user["id"] if user else None,
            user["id"] if user else None,
            now,
            now,
        ],
    )
    audit("create", "services", record_id, title)
    return record_id


def save_document(item: sqlite3.Row | None = None) -> int:
    now = utc_now()
    user = current_user()
    title = request.form.get("title", "").strip()
    file_path = item["file_path"] if item else ""
    file = request.files.get("document_file")
    if file and file.filename:
        file_path = save_upload(file, "documents", ALLOWED_DOCUMENTS)
    year = request.form.get("year", "").strip()
    values = {
        "title": title,
        "slug": unique_slug(request.form.get("slug", "").strip() or title, "documents", item["id"] if item else None),
        "category": request.form.get("category", "otros"),
        "description": request.form.get("description", "").strip(),
        "document_date": request.form.get("document_date", "").strip(),
        "year": int(year) if year.isdigit() else None,
        "department": request.form.get("department", "").strip(),
        "file_path": file_path,
        "external_url": request.form.get("external_url", "").strip(),
        "status": request.form.get("status", "draft"),
        "tags": clean_tags(request.form.get("tags", "")),
        "updated_by": user["id"] if user else None,
        "updated_at": now,
    }
    if item:
        before = dict(item)
        execute(
            """
            UPDATE documents SET title=?, slug=?, category=?, description=?, document_date=?, year=?,
            department=?, file_path=?, external_url=?, status=?, tags=?, updated_by=?, updated_at=?
            WHERE id=?
            """,
            list(values.values()) + [item["id"]],
        )
        audit("update", "documents", item["id"], title, changed_fields(before, values))
        return int(item["id"])
    record_id = execute(
        """
        INSERT INTO documents
        (title, slug, category, description, document_date, year, department, file_path, external_url,
        status, tags, created_by, updated_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            values["title"],
            values["slug"],
            values["category"],
            values["description"],
            values["document_date"],
            values["year"],
            values["department"],
            values["file_path"],
            values["external_url"],
            values["status"],
            values["tags"],
            user["id"] if user else None,
            user["id"] if user else None,
            now,
            now,
        ],
    )
    audit("create", "documents", record_id, title)
    return record_id


def save_mayor(item: sqlite3.Row | None = None) -> int:
    now = utc_now()
    user = current_user()
    name = request.form.get("name", "").strip()
    photo_path = item["photo_path"] if item else ""
    file = request.files.get("photo_file")
    if file and file.filename:
        photo_path = save_upload(file, "images", ALLOWED_IMAGES)
    is_current = 1 if request.form.get("is_current") == "on" else 0
    if is_current:
        execute("UPDATE mayors SET is_current = 0")
    values = {
        "name": name,
        "slug": unique_slug(request.form.get("slug", "").strip() or name, "mayors", item["id"] if item else None),
        "period_start": request.form.get("period_start", "").strip(),
        "period_end": request.form.get("period_end", "").strip(),
        "biography": request.form.get("biography", "").strip(),
        "photo_path": photo_path,
        "is_current": is_current,
        "status": request.form.get("status", "draft"),
        "tags": clean_tags(request.form.get("tags", "")),
        "updated_by": user["id"] if user else None,
        "updated_at": now,
    }
    if item:
        before = dict(item)
        execute(
            """
            UPDATE mayors SET name=?, slug=?, period_start=?, period_end=?, biography=?, photo_path=?,
            is_current=?, status=?, tags=?, updated_by=?, updated_at=? WHERE id=?
            """,
            list(values.values()) + [item["id"]],
        )
        audit("update", "mayors", item["id"], name, changed_fields(before, values))
        return int(item["id"])
    record_id = execute(
        """
        INSERT INTO mayors
        (name, slug, period_start, period_end, biography, photo_path, is_current, status, tags,
        created_by, updated_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            values["name"],
            values["slug"],
            values["period_start"],
            values["period_end"],
            values["biography"],
            values["photo_path"],
            values["is_current"],
            values["status"],
            values["tags"],
            user["id"] if user else None,
            user["id"] if user else None,
            now,
            now,
        ],
    )
    audit("create", "mayors", record_id, name)
    return record_id


def save_user(item: sqlite3.Row | None = None) -> int:
    now = utc_now()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "editor")
    status = request.form.get("status", "active")
    if item:
        before = dict(item)
        if password:
            execute(
                "UPDATE users SET name=?, email=?, password_hash=?, role=?, status=?, updated_at=? WHERE id=?",
                [name, email, generate_password_hash(password), role, status, now, item["id"]],
            )
        else:
            execute(
                "UPDATE users SET name=?, email=?, role=?, status=?, updated_at=? WHERE id=?",
                [name, email, role, status, now, item["id"]],
            )
        audit("update", "users", item["id"], name, changed_fields(before, {"name": name, "email": email, "role": role, "status": status}))
        return int(item["id"])
    record_id = execute(
        """
        INSERT INTO users (name, email, password_hash, role, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [name, email, generate_password_hash(password), role, status, now, now],
    )
    audit("create", "users", record_id, name)
    return record_id


def save_upload(file: Any, folder: str, allowed: set[str]) -> str:
    filename = secure_filename(file.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in allowed:
        abort(400, f"Tipo de archivo no permitido: .{extension}")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    final_name = f"{stamp}-{filename}"
    storage_path = f"{folder}/{final_name}"
    if USE_SUPABASE_STORAGE:
        return save_supabase_upload(file, storage_path)
    target_dir = UPLOAD_DIR / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    file.save(target_dir / final_name)
    return storage_path


def get_supabase_storage_client() -> Any:
    global SUPABASE_STORAGE_CLIENT
    if create_client is None:
        raise RuntimeError("Falta instalar supabase para usar Supabase Storage.")
    if SUPABASE_STORAGE_CLIENT is None:
        SUPABASE_STORAGE_CLIENT = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return SUPABASE_STORAGE_CLIENT


def save_supabase_upload(file: Any, storage_path: str) -> str:
    file.seek(0)
    content = file.read()
    client = get_supabase_storage_client()
    client.storage.from_(SUPABASE_BUCKET).upload(
        path=storage_path,
        file=content,
        file_options={
            "content-type": file.mimetype or "application/octet-stream",
            "cache-control": "3600",
            "upsert": "true",
        },
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"


def asset_url(path: str | None) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return url_for("uploads", filename=path)


def clean_tags(raw: str) -> str:
    reader = csv.reader(io.StringIO(raw))
    tags = next(reader, []) if raw else []
    clean = []
    for tag in tags:
        normalized = " ".join(tag.strip().lower().split())
        if normalized and normalized not in clean:
            clean.append(normalized)
    return ", ".join(clean[:4])


def split_tags(value: str | None) -> list[str]:
    return [tag.strip() for tag in (value or "").split(",") if tag.strip()]


def trending_tags() -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for table in ["content", "services", "documents", "mayors"]:
        for row in query_all(f"SELECT tags FROM {table} WHERE status = 'published'"):
            for tag in split_tags(row["tags"]):
                counts[tag] = counts.get(tag, 0) + 1
    return [{"name": key, "count": value} for key, value in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:5]]


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFD", value.lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return "".join(char if char.isalnum() or char.isspace() else " " for char in text)


def search_records(query: str, tag: str) -> list[dict[str, str]]:
    needle = normalize_text(tag or query)
    if not needle:
        return []
    results: list[dict[str, str]] = []
    sources = [
        ("content", "Actualidad", "title", "summary", "tags", "actualidad_detail"),
        ("services", "Trámite", "title", "summary", "tags", "tramite_detail"),
        ("documents", "Transparencia", "title", "description", "tags", "document_detail"),
        ("mayors", "Municipalidad", "name", "biography", "tags", "mayor_detail"),
    ]
    for table, label, title_field, summary_field, tag_field, endpoint in sources:
        for row in query_all(f"SELECT * FROM {table} WHERE status = 'published'"):
            haystack = normalize_text(" ".join(str(row[key] or "") for key in row.keys()))
            if needle in haystack:
                url = url_for(endpoint, slug=row["slug"])
                results.append(
                    {
                        "label": label,
                        "title": row[title_field],
                        "summary": row[summary_field] or "",
                        "url": url,
                        "tags": row[tag_field] or "",
                    }
                )
    return results


def slugify(value: str) -> str:
    text = normalize_text(value)
    parts = [part for part in text.split() if part]
    return "-".join(parts) or "contenido"


def unique_slug(value: str, table: str, current_id: int | None = None) -> str:
    base = slugify(value)
    slug = base
    counter = 2
    while True:
        row = query_one(f"SELECT id FROM {table} WHERE slug = ?", [slug])
        if not row or (current_id and row["id"] == current_id):
            return slug
        slug = f"{base}-{counter}"
        counter += 1


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> str:
    changed = [key for key, value in after.items() if key in before and str(before[key] or "") != str(value or "")]
    return ", ".join(changed) if changed else "Sin cambios relevantes."


def audit(action: str, entity_type: str, entity_id: int | None, entity_title: str, details: str = "") -> None:
    user = current_user()
    execute(
        """
        INSERT INTO audit_logs
        (user_id, user_email, action, entity_type, entity_id, entity_title, details, ip, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            user["id"] if user else None,
            user["email"] if user else "",
            action,
            entity_type,
            entity_id,
            entity_title,
            details,
            request.headers.get("X-Forwarded-For", request.remote_addr or ""),
            request.headers.get("User-Agent", "")[:220],
            utc_now(),
        ],
    )


def sample_history() -> str:
    return (
        "Marcala es un municipio del departamento de La Paz reconocido por su actividad cafetalera, "
        "su vida comunitaria y su entorno de montaña. Esta sección está preparada para que el equipo municipal "
        "publique una reseña histórica oficial, hitos relevantes, fotografías y referencias documentales."
    )


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)
