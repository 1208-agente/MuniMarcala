const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
};

const TABLES = {
  content: {
    order: "updated_at.desc",
    writable: [
      "kind", "title", "slug", "category", "summary", "body", "image_path", "image_alt",
      "published_at", "event_date", "status", "tags", "cta_label", "cta_url",
    ],
  },
  services: {
    order: "updated_at.desc",
    writable: [
      "title", "slug", "department", "summary", "requirements", "steps", "cost",
      "estimated_time", "schedule", "location", "contact", "document_url", "status", "tags",
    ],
  },
  documents: {
    order: "document_date.desc",
    writable: [
      "title", "slug", "category", "description", "document_date", "year", "department",
      "file_path", "external_url", "status", "tags",
    ],
  },
  mayors: {
    order: "is_current.desc,period_start.desc",
    writable: [
      "name", "slug", "period_start", "period_end", "biography", "photo_path",
      "is_current", "status", "tags",
    ],
  },
  municipal_authorities: {
    order: "sort_order.asc,name.asc",
    writable: [
      "name", "slug", "position", "area", "period", "phone", "email", "biography",
      "photo_path", "sort_order", "status", "tags",
    ],
  },
  contacts: {
    order: "sort_order.asc,area.asc,name.asc",
    writable: [
      "name", "slug", "area", "position", "phone", "email", "office", "bio",
      "photo_path", "sort_order", "status", "tags",
    ],
  },
  civic_requests: {
    order: "created_at.desc",
    writable: ["request_status", "internal_notes"],
  },
  settings: {
    order: "key.asc",
    writable: ["key", "value"],
  },
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    try {
      if (url.pathname === "/admin" || url.pathname === "/admin/" || url.pathname === "/admin/login") {
        return env.ASSETS.fetch(new Request(new URL("/_panel/index.html", url), request));
      }

      if (url.pathname.startsWith("/api/")) {
        return await handleApi(request, env, url);
      }

      if (url.pathname === "/participacion" && request.method === "POST") {
        return await handlePublicCivicRequest(request, env);
      }

      return env.ASSETS.fetch(request);
    } catch (error) {
      return json({ error: "Error interno", detail: error.message }, 500);
    }
  },
};

async function handleApi(request, env, url) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders() });

  if (url.pathname === "/api/auth/login" && request.method === "POST") {
    return login(request, env);
  }

  if (url.pathname === "/api/diagnostico" && request.method === "GET") {
    return json({
      supabase_url_configurada: Boolean(env.SUPABASE_URL),
      supabase_host: safeHost(env.SUPABASE_URL),
      anon_key_configurada: Boolean(env.SUPABASE_ANON_KEY),
      service_role_configurada: Boolean(env.SUPABASE_SERVICE_ROLE_KEY),
      bucket: env.SUPABASE_BUCKET || "",
    });
  }

  const user = await requireAdmin(request, env);
  if (!user.ok) return user.response;

  if (url.pathname === "/api/auth/me" && request.method === "GET") {
    return json({ user: user.profile });
  }

  if (url.pathname === "/api/upload" && request.method === "POST") {
    return uploadFile(request, env, user.profile);
  }

  const match = url.pathname.match(/^\/api\/([a-z_]+)(?:\/(\d+))?$/);
  if (!match) return json({ error: "Ruta no encontrada" }, 404);

  const [, table, id] = match;
  if (!TABLES[table]) return json({ error: "Recurso no permitido" }, 404);

  if (request.method === "GET") return listRows(env, table, url);
  if (request.method === "POST" && !id) return createRow(request, env, table, user.profile);
  if (request.method === "PATCH" && id) return updateRow(request, env, table, id, user.profile);

  return json({ error: "Método no permitido" }, 405);
}

async function login(request, env) {
  const { email, password } = await request.json();
  if (!email || !password) return json({ error: "Correo y contraseña son requeridos." }, 400);

  let auth;
  try {
    auth = await supabaseAuth(env, "/auth/v1/token?grant_type=password", {
      method: "POST",
      key: env.SUPABASE_ANON_KEY,
      body: { email, password },
    });
  } catch (error) {
    return json({ error: error.message || "Supabase rechazó el inicio de sesión." }, 401);
  }

  if (!auth.access_token || !auth.user?.email) {
    return json({ error: "No se pudo iniciar sesión." }, 401);
  }

  let profile = await getProfileByEmail(env, auth.user.email);
  if (!profile) return json({ error: "El usuario existe en Supabase, pero no está habilitado en el panel municipal." }, 403);
  if (profile.status !== "active") return json({ error: "Este usuario está pausado." }, 403);

  if (!profile.supabase_user_id) {
    const updated = await supabaseRest(env, `/rest/v1/users?email=eq.${encodeURIComponent(auth.user.email)}&select=*`, {
      method: "PATCH",
      body: { supabase_user_id: auth.user.id, updated_at: nowIso() },
      prefer: "return=representation",
    });
    profile = updated[0] || profile;
  }

  await audit(env, profile, "login", "users", profile.id, profile.name, "Inicio de sesión en Cloudflare.");

  return json({
    access_token: auth.access_token,
    refresh_token: auth.refresh_token,
    expires_in: auth.expires_in,
    user: publicProfile(profile),
  });
}

async function requireAdmin(request, env) {
  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) return { ok: false, response: json({ error: "Sesión requerida." }, 401) };

  const authUser = await supabaseAuth(env, "/auth/v1/user", {
    method: "GET",
    key: env.SUPABASE_ANON_KEY,
    token,
  }).catch(() => null);

  if (!authUser?.email) return { ok: false, response: json({ error: "Sesión inválida." }, 401) };

  const profile = await getProfileByEmail(env, authUser.email);
  if (!profile || profile.status !== "active") {
    return { ok: false, response: json({ error: "Usuario sin permiso activo." }, 403) };
  }

  return { ok: true, profile };
}

async function getProfileByEmail(env, email) {
  const rows = await supabaseRest(env, `/rest/v1/users?email=eq.${encodeURIComponent(email)}&select=*`);
  return rows[0] || null;
}

async function listRows(env, table, url) {
  const config = TABLES[table];
  const limit = Math.min(Number(url.searchParams.get("limit") || "100"), 200);
  const params = new URLSearchParams({ select: "*", limit: String(limit) });
  if (config.order) {
    for (const part of config.order.split(",")) params.append("order", part.trim());
  }
  if (url.searchParams.get("status")) params.set("status", `eq.${url.searchParams.get("status")}`);
  if (url.searchParams.get("category")) params.set("category", `eq.${url.searchParams.get("category")}`);
  const rows = await supabaseRest(env, `/rest/v1/${table}?${params.toString()}`);
  return json({ rows });
}

async function createRow(request, env, table, user) {
  const payload = cleanPayload(await request.json(), table);
  const timestamp = nowIso();
  if (table !== "settings") {
    payload.created_at = payload.created_at || timestamp;
    payload.updated_at = timestamp;
    if ("created_by" in payload || TABLES[table].writable.includes("title") || TABLES[table].writable.includes("name")) {
      payload.created_by = user.id;
      payload.updated_by = user.id;
    }
  }
  const rows = await supabaseRest(env, `/rest/v1/${table}?select=*`, {
    method: "POST",
    body: payload,
    prefer: "return=representation",
  });
  const row = rows[0];
  await audit(env, user, "create", table, row?.id, row?.title || row?.name || row?.key || "Registro", "");
  return json({ row }, 201);
}

async function updateRow(request, env, table, id, user) {
  const payload = cleanPayload(await request.json(), table);
  if (table !== "settings") {
    payload.updated_at = nowIso();
    if (TABLES[table].writable.includes("title") || TABLES[table].writable.includes("name")) {
      payload.updated_by = user.id;
    }
  }
  const rows = await supabaseRest(env, `/rest/v1/${table}?id=eq.${id}&select=*`, {
    method: "PATCH",
    body: payload,
    prefer: "return=representation",
  });
  const row = rows[0];
  await audit(env, user, "update", table, Number(id), row?.title || row?.name || row?.key || "Registro", "");
  return json({ row });
}

function cleanPayload(payload, table) {
  const allowed = new Set(TABLES[table].writable);
  const output = {};
  for (const [key, value] of Object.entries(payload || {})) {
    if (!allowed.has(key)) continue;
    if (value === "") {
      output[key] = null;
    } else if (["year", "is_current", "sort_order"].includes(key)) {
      output[key] = Number(value || 0);
    } else {
      output[key] = value;
    }
  }
  return output;
}

async function uploadFile(request, env, user) {
  const data = await request.formData();
  const file = data.get("file");
  const folder = sanitizeFolder(data.get("folder") || "attachments");
  if (!file || typeof file === "string") return json({ error: "Archivo requerido." }, 400);
  if (file.size > 10 * 1024 * 1024) return json({ error: "El archivo no debe superar 10 MB." }, 400);

  const path = await uploadBlob(env, file, folder);

  await audit(env, user, "upload", "storage", null, file.name, path);

  return json({
    file_path: path,
    public_url: `${env.SUPABASE_URL}/storage/v1/object/public/${env.SUPABASE_BUCKET}/${path}`,
  });
}

async function handlePublicCivicRequest(request, env) {
  const form = await request.formData();
  const timestamp = nowIso();
  const subject = String(form.get("subject") || "").trim();
  const body = String(form.get("body") || "").trim();
  if (!subject || !body) return json({ error: "Asunto y descripción son requeridos." }, 400);

  const rows = await supabaseRest(env, "/rest/v1/civic_requests?select=*", {
    method: "POST",
    body: {
      folio: `MRC-${Date.now()}`,
      request_type: String(form.get("request_type") || "peticion"),
      subject,
      body,
      wants_response: form.get("wants_response") ? 1 : 0,
      requester_name: String(form.get("requester_name") || ""),
      requester_phone: String(form.get("requester_phone") || ""),
      requester_email: String(form.get("requester_email") || ""),
      request_status: "nuevo",
      created_at: timestamp,
      updated_at: timestamp,
    },
    prefer: "return=representation",
  });

  const record = rows[0];
  const attachments = form.getAll("attachment_files").filter((file) => file && typeof file !== "string" && file.size > 0);
  for (const file of attachments.slice(0, 3)) {
    if (file.size > 10 * 1024 * 1024) continue;
    const filePath = await uploadBlob(env, file, "attachments");
    await supabaseRest(env, "/rest/v1/civic_request_attachments", {
      method: "POST",
      body: {
        request_id: record.id,
        title: file.name || "Archivo de respaldo",
        file_path: filePath,
        file_type: file.type || "",
        created_at: timestamp,
      },
    });
  }

  return html(`
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Solicitud recibida | Municipalidad de Marcala</title>
      <link rel="stylesheet" href="/static/css/styles.css">
    </head>
    <body>
      <main class="section">
        <article class="detail-card">
          <p class="eyebrow">Participación ciudadana</p>
          <h1>Solicitud recibida</h1>
          <p>Tu información fue enviada a la Municipalidad de Marcala.</p>
          <p><strong>Folio:</strong> ${escapeHtml(record.folio)}</p>
          <a class="button" href="/">Volver al inicio</a>
        </article>
      </main>
    </body>
    </html>
  `, 201);
}

async function uploadBlob(env, file, folder) {
  const safeName = sanitizeFileName(file.name || "archivo");
  const path = `${folder}/${new Date().toISOString().slice(0, 10)}/${Date.now()}-${safeName}`;
  const storagePath = `/storage/v1/object/${env.SUPABASE_BUCKET}/${path}`;

  const response = await fetch(`${env.SUPABASE_URL}${storagePath}`, {
    method: "POST",
    headers: {
      apikey: env.SUPABASE_SERVICE_ROLE_KEY,
      authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      "content-type": file.type || "application/octet-stream",
      "x-upsert": "true",
    },
    body: file.stream(),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`No se pudo subir el archivo: ${detail}`);
  }

  return path;
}

async function supabaseRest(env, path, options = {}) {
  return supabaseFetch(env, path, {
    method: options.method || "GET",
    key: env.SUPABASE_SERVICE_ROLE_KEY,
    token: env.SUPABASE_SERVICE_ROLE_KEY,
    body: options.body,
    prefer: options.prefer,
  });
}

async function supabaseAuth(env, path, options = {}) {
  return supabaseFetch(env, path, options);
}

async function supabaseFetch(env, path, options = {}) {
  if (!env.SUPABASE_URL) throw new Error("Falta SUPABASE_URL.");
  const key = options.key || env.SUPABASE_SERVICE_ROLE_KEY;
  const headers = {
    apikey: key,
    authorization: `Bearer ${options.token || key}`,
  };
  if (options.body) headers["content-type"] = "application/json";
  if (options.prefer) headers.prefer = options.prefer;

  const response = await fetch(`${env.SUPABASE_URL}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = data.message || data.error_description || data.error || text || "Supabase error";
    throw new Error(message);
  }
  return data;
}

async function audit(env, user, action, entityType, entityId, title, details) {
  await supabaseRest(env, "/rest/v1/audit_logs", {
    method: "POST",
    body: {
      user_id: user?.id || null,
      user_email: user?.email || "",
      action,
      entity_type: entityType,
      entity_id: entityId || null,
      entity_title: title || "",
      details: details || "",
      ip: "",
      user_agent: "",
      created_at: nowIso(),
    },
  }).catch(() => null);
}

function publicProfile(profile) {
  return {
    id: profile.id,
    name: profile.name,
    email: profile.email,
    role: profile.role,
    status: profile.status,
  };
}

function sanitizeFolder(value) {
  const folder = String(value).toLowerCase().replace(/[^a-z0-9_-]/g, "");
  return ["images", "documents", "attachments"].includes(folder) ? folder : "attachments";
}

function sanitizeFileName(value) {
  return String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9._-]/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 120);
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function safeHost(value) {
  try {
    return value ? new URL(value).host : "";
  } catch {
    return "URL inválida";
  }
}

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { ...JSON_HEADERS, ...corsHeaders() },
  });
}

function html(markup, status = 200) {
  return new Response(markup, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,PATCH,OPTIONS",
    "access-control-allow-headers": "authorization,content-type",
  };
}
