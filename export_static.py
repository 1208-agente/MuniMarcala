from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from app import CONTENT_CATEGORIES, DOCUMENT_CATEGORIES, UPLOAD_DIR, app, query_all, split_tags


BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR / "public_build"


def main() -> None:
    if BUILD_DIR.exists():
        clear_directory(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    copy_tree(BASE_DIR / "static", BUILD_DIR / "static")
    copy_tree(UPLOAD_DIR, BUILD_DIR / "uploads")

    routes = public_routes()
    with app.test_client() as client:
        for route in routes:
            response = client.get(route)
            if response.status_code != 200:
                raise RuntimeError(f"{route} returned {response.status_code}")
            html = rewrite_html(response.get_data(as_text=True))
            write_route(route, html)

    write_search_index()
    write_static_search_js()
    write_cloudflare_files()
    print(f"Static public site exported to: {BUILD_DIR}")


def public_routes() -> list[str]:
    routes = [
        "/",
        "/tramites",
        "/actualidad",
        "/transparencia",
        "/municipalidad",
        "/contactos",
        "/participacion",
        "/agenda",
        "/privacidad",
        "/buscar",
    ]
    routes.extend(f"/actualidad?categoria={key}" for key, _ in CONTENT_CATEGORIES)
    routes.extend(f"/transparencia?categoria={key}" for key, _ in DOCUMENT_CATEGORIES)
    routes.extend(f"/actualidad/{row['slug']}" for row in query_all("SELECT slug FROM content WHERE status='published'"))
    routes.extend(f"/tramites/{row['slug']}" for row in query_all("SELECT slug FROM services WHERE status='published'"))
    routes.extend(f"/transparencia/{row['slug']}" for row in query_all("SELECT slug FROM documents WHERE status='published'"))
    routes.extend(f"/municipalidad/alcaldes/{row['slug']}" for row in query_all("SELECT slug FROM mayors WHERE status='published'"))
    routes.extend(f"/municipalidad/autoridades/{row['slug']}" for row in query_all("SELECT slug FROM municipal_authorities WHERE status='published'"))
    routes.extend(f"/contactos/{row['slug']}" for row in query_all("SELECT slug FROM contacts WHERE status='published'"))
    return dedupe(routes)


def write_route(route: str, html: str) -> None:
    path, _, query = route.partition("?")
    if path == "/":
        output = BUILD_DIR / "index.html"
    else:
        folder = path.strip("/")
        if query:
            folder = f"{folder}/{safe_query(query)}"
        output = BUILD_DIR / folder / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def rewrite_html(html: str) -> str:
    html = html.replace('href="/admin/login"', 'href="/"')
    html = html.replace('href="/admin"', 'href="/"')
    html = html.replace('>Acceso interno<', '>Inicio<')
    html = html.replace('src="/static/', 'src="/static/')
    html = html.replace('href="/static/', 'href="/static/')
    return html


def write_search_index() -> None:
    records: list[dict[str, str]] = []
    sources = [
        ("content", "Actualidad", "title", "summary", "body", "/actualidad/{slug}"),
        ("services", "Trámite", "title", "summary", "requirements", "/tramites/{slug}"),
        ("documents", "Transparencia", "title", "description", "department", "/transparencia/{slug}"),
        ("mayors", "Municipalidad", "name", "biography", "period_start", "/municipalidad/alcaldes/{slug}"),
        ("municipal_authorities", "Autoridad municipal", "name", "biography", "position", "/municipalidad/autoridades/{slug}"),
        ("contacts", "Contacto", "name", "position", "area", "/contactos/{slug}"),
    ]
    for table, label, title_field, summary_field, body_field, url_template in sources:
        for row in query_all(f"SELECT * FROM {table} WHERE status='published'"):
            url = url_template.format(slug=row["slug"]) if "{slug}" in url_template else url_template
            records.append(
                {
                    "type": label,
                    "title": row[title_field] or "",
                    "summary": row[summary_field] or "",
                    "body": row[body_field] or "",
                    "tags": ", ".join(split_tags(row["tags"] if "tags" in row.keys() else "")),
                    "url": url,
                }
            )
    (BUILD_DIR / "search-index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_static_search_js() -> None:
    target = BUILD_DIR / "static" / "js" / "static-search.js"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """
const normalize = (value) => (value || "")
  .toLowerCase()
  .normalize("NFD")
  .replace(/[\\u0300-\\u036f]/g, "")
  .replace(/[^a-z0-9\\s]/g, " ");

async function runStaticSearch() {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q") || params.get("tag") || "";
  const input = document.querySelector(".wide-search input[name='q']");
  const list = document.querySelector("[data-static-results]");
  const title = document.querySelector("[data-static-search-title]");
  if (!list) return;
  if (input) input.value = q;
  if (title) title.textContent = q || "Buscar";

  const response = await fetch("/search-index.json");
  const records = await response.json();
  const needle = normalize(q);
  if (!needle) {
    list.innerHTML = "<p>Escribe una palabra o frase para buscar en el sitio.</p>";
    return;
  }

  const matches = records.filter((record) => normalize([
    record.type, record.title, record.summary, record.body, record.tags
  ].join(" ")).includes(needle));

  list.innerHTML = matches.length
    ? matches.map((item) => `
      <a class="document-row" href="${item.url}">
        <span>${item.type}</span>
        <strong>${item.title}</strong>
        <p>${item.summary || ""}</p>
        ${item.tags ? `<small>${item.tags}</small>` : ""}
      </a>
    `).join("")
    : "<p>No se encontraron resultados.</p>";
}

runStaticSearch();
""".strip()
        + "\n",
        encoding="utf-8",
    )

    search_page = BUILD_DIR / "buscar" / "index.html"
    if search_page.exists():
        html = search_page.read_text(encoding="utf-8")
        html = re.sub(r"<h1>.*?</h1>", '<h1 data-static-search-title>Buscar</h1>', html, count=1, flags=re.S)
        html = re.sub(
            r'<div class="document-list">.*?</div>',
            '<div class="document-list" data-static-results><p>Escribe una palabra o frase para buscar en el sitio.</p></div>',
            html,
            count=1,
            flags=re.S,
        )
        html = html.replace("</body>", '  <script src="/static/js/static-search.js"></script>\n</body>')
        search_page.write_text(html, encoding="utf-8")


def write_cloudflare_files() -> None:
    (BUILD_DIR / "wrangler.jsonc").write_text(
        """
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "munimarcala",
  "compatibility_date": "2026-05-17",
  "observability": {
    "enabled": true
  },
  "assets": {
    "directory": "."
  }
}
""".lstrip(),
        encoding="utf-8",
    )
    (BUILD_DIR / "_headers").write_text(
        """
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
""".lstrip(),
        encoding="utf-8",
    )
    (BUILD_DIR / "_redirects").write_text(
        """
/buscar /buscar/index.html 200
""".lstrip(),
        encoding="utf-8",
    )
    (BUILD_DIR / ".assetsignore").write_text(
        """
.git
.git/**
.wrangler
.wrangler/**
node_modules
node_modules/**
*.log
""".lstrip(),
        encoding="utf-8",
    )


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    shutil.copytree(source, target, dirs_exist_ok=True)


def clear_directory(path: Path) -> None:
    for child in path.iterdir():
        if child.name == "admin":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def safe_query(query: str) -> str:
    return query.replace("=", "-").replace("&", "_").replace("/", "-")


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


if __name__ == "__main__":
    main()
