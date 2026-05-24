const TOKEN_KEY = "munimarcala_admin_token";

const resources = {
  content: {
    label: "Actualidad y agenda",
    title: "title",
    subtitle: "category",
    upload: true,
    fields: [
      ["kind", "Tipo", "select", ["actualidad", "agenda"]],
      ["status", "Estado", "select", ["draft", "published", "archived"]],
      ["title", "Título", "text"],
      ["slug", "Enlace interno", "text"],
      ["category", "Categoría", "text"],
      ["published_at", "Fecha de publicación", "date"],
      ["event_date", "Fecha de evento", "datetime-local"],
      ["summary", "Resumen", "textarea"],
      ["body", "Contenido", "textarea"],
      ["image_path", "Ruta de imagen", "text"],
      ["image_alt", "Texto alternativo", "text"],
      ["tags", "Etiquetas", "text"],
      ["cta_label", "Texto del botón", "text"],
      ["cta_url", "Enlace del botón", "url"],
    ],
  },
  services: {
    label: "Trámites",
    title: "title",
    subtitle: "department",
    fields: [
      ["status", "Estado", "select", ["draft", "published", "archived"]],
      ["title", "Título", "text"],
      ["slug", "Enlace interno", "text"],
      ["department", "Departamento", "text"],
      ["summary", "Resumen", "textarea"],
      ["requirements", "Requisitos", "textarea"],
      ["steps", "Pasos", "textarea"],
      ["cost", "Costo", "text"],
      ["estimated_time", "Tiempo estimado", "text"],
      ["schedule", "Horario", "text"],
      ["location", "Ubicación", "text"],
      ["contact", "Contacto", "text"],
      ["document_url", "Documento o enlace", "text"],
      ["tags", "Etiquetas", "text"],
    ],
  },
  documents: {
    label: "Transparencia",
    title: "title",
    subtitle: "category",
    upload: true,
    fields: [
      ["status", "Estado", "select", ["draft", "published", "archived"]],
      ["title", "Título", "text"],
      ["slug", "Enlace interno", "text"],
      ["category", "Categoría", "text"],
      ["document_date", "Fecha del documento", "date"],
      ["year", "Año", "number"],
      ["department", "Departamento", "text"],
      ["description", "Descripción", "textarea"],
      ["file_path", "Archivo", "text"],
      ["external_url", "Enlace externo", "url"],
      ["tags", "Etiquetas", "text"],
    ],
  },
  municipal_authorities: {
    label: "Corporación municipal",
    title: "name",
    subtitle: "position",
    upload: true,
    fields: [
      ["status", "Estado", "select", ["draft", "published", "archived"]],
      ["name", "Nombre", "text"],
      ["slug", "Enlace interno", "text"],
      ["position", "Cargo", "text"],
      ["area", "Área", "text"],
      ["period", "Periodo", "text"],
      ["phone", "Teléfono", "tel"],
      ["email", "Correo", "email"],
      ["biography", "Biografía", "textarea"],
      ["photo_path", "Foto", "text"],
      ["sort_order", "Orden", "number"],
      ["tags", "Etiquetas", "text"],
    ],
  },
  mayors: {
    label: "Historial de alcaldes",
    title: "name",
    subtitle: "period_start",
    upload: true,
    fields: [
      ["status", "Estado", "select", ["draft", "published", "archived"]],
      ["name", "Nombre", "text"],
      ["slug", "Enlace interno", "text"],
      ["period_start", "Inicio de periodo", "text"],
      ["period_end", "Fin de periodo", "text"],
      ["biography", "Biografía", "textarea"],
      ["photo_path", "Foto", "text"],
      ["is_current", "Persona actual", "number"],
      ["tags", "Etiquetas", "text"],
    ],
  },
  contacts: {
    label: "Contactos",
    title: "name",
    subtitle: "area",
    upload: true,
    fields: [
      ["status", "Estado", "select", ["draft", "published", "archived"]],
      ["name", "Nombre", "text"],
      ["slug", "Enlace interno", "text"],
      ["area", "Área", "text"],
      ["position", "Cargo", "text"],
      ["phone", "Teléfono", "tel"],
      ["email", "Correo", "email"],
      ["office", "Oficina", "text"],
      ["bio", "Descripción", "textarea"],
      ["photo_path", "Foto", "text"],
      ["sort_order", "Orden", "number"],
      ["tags", "Etiquetas", "text"],
    ],
  },
  civic_requests: {
    label: "Denuncias y peticiones",
    title: "subject",
    subtitle: "request_status",
    fields: [
      ["request_status", "Estado", "select", ["nuevo", "en_tramite", "resuelto", "irrelevante"]],
      ["internal_notes", "Notas internas", "textarea"],
    ],
  },
  audit_logs: {
    label: "Auditoría",
    title: "entity_title",
    subtitle: "user_email",
    readOnly: true,
    exportFields: [
      ["created_at", "Fecha"],
      ["user_email", "Usuario"],
      ["action", "Acción"],
      ["entity_type", "Sección"],
      ["entity_id", "ID contenido"],
      ["entity_title", "Contenido"],
      ["details", "Detalle"],
      ["ip", "IP"],
      ["user_agent", "Navegador"],
    ],
    fields: [
      ["created_at", "Fecha"],
      ["user_email", "Usuario"],
      ["action", "Acción"],
      ["entity_type", "Sección"],
      ["entity_id", "ID contenido"],
      ["entity_title", "Contenido"],
      ["details", "Detalle"],
      ["ip", "IP"],
      ["user_agent", "Navegador"],
    ],
  },
};

let currentResource = "content";
let currentRecord = null;
let rows = [];

const $ = (selector) => document.querySelector(selector);
const loginPanel = $("[data-login-panel]");
const dashboard = $("[data-dashboard]");
const tabs = $("[data-tabs]");
const list = $("[data-record-list]");
const fields = $("[data-fields]");
const auditFilters = $("[data-audit-filters]");
const exportButton = $("[data-export]");

init();

function init() {
  renderTabs();
  $("[data-login-form]").addEventListener("submit", onLogin);
  $("[data-editor-form]").addEventListener("submit", onSave);
  $("[data-refresh]").addEventListener("click", loadRows);
  $("[data-new]").addEventListener("click", () => editRecord({}));
  $("[data-filter]").addEventListener("input", renderList);
  $("[data-export]").addEventListener("click", exportRows);
  $("[data-logout]").addEventListener("click", logout);
  $("[data-upload-button]").addEventListener("click", uploadFile);
  auditFilters.querySelectorAll("input, select").forEach((control) => {
    control.addEventListener("change", loadRows);
    control.addEventListener("input", debounce(loadRows, 350));
  });

  if (localStorage.getItem(TOKEN_KEY)) {
    showDashboard();
    loadRows();
  }
}

function renderTabs() {
  tabs.innerHTML = Object.entries(resources).map(([key, config]) => `
    <button type="button" data-tab="${key}">${config.label}</button>
  `).join("");
  tabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-tab]");
    if (!button) return;
    currentResource = button.dataset.tab;
    currentRecord = null;
    loadRows();
  });
}

async function onLogin(event) {
  event.preventDefault();
  const loginForm = event.currentTarget;
  const submitButton = loginForm.querySelector("button[type='submit']");
  const form = new FormData(loginForm);
  const message = $("[data-login-message]");
  message.textContent = "Validando credenciales...";
  if (submitButton) submitButton.disabled = true;
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: {
        email: form.get("email"),
        password: form.get("password"),
      },
      public: true,
    });
    if (data.ok === false) throw new Error(data.error || "No se pudo iniciar sesión.");
    if (!data.access_token) throw new Error("Supabase no devolvió una sesión válida.");
    message.textContent = "Abriendo panel...";
    localStorage.setItem(TOKEN_KEY, data.access_token);
    clearLoginForm(loginForm);
    showDashboard(data.user || { email: form.get("email"), role: "usuario" });
    loadRows().catch((error) => {
      $("[data-record-list]").innerHTML = `<p class="message">${escapeHtml(error.message)}</p>`;
    });
  } catch (error) {
    message.textContent = error.message;
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

function showDashboard(user = null) {
  loginPanel.hidden = true;
  loginPanel.classList.add("is-hidden");
  dashboard.hidden = false;
  dashboard.classList.remove("is-hidden");
  if (user) $("[data-user-label]").textContent = `${user.name} · ${user.role}`;
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  dashboard.hidden = true;
  dashboard.classList.add("is-hidden");
  loginPanel.hidden = false;
  loginPanel.classList.remove("is-hidden");
  const loginForm = $("[data-login-form]");
  clearLoginForm(loginForm);
  $("[data-login-message]").textContent = "";
}

function clearLoginForm(form) {
  if (!form) return;
  const email = form.querySelector("[name='email']");
  const password = form.querySelector("[name='password']");
  if (email) email.value = "";
  if (password) password.value = "";
}

async function loadRows() {
  setActiveTab();
  const config = resources[currentResource];
  $("[data-section-title]").textContent = config.label;
  $("[data-section-kind]").textContent = currentResource;
  syncResourceUi(config);
  list.innerHTML = "<p>Cargando...</p>";
  try {
    const data = await api(`/api/${currentResource}${resourceQuery()}`);
    rows = data.rows || [];
    renderList();
    editRecord(rows[0] || {});
  } catch (error) {
    list.innerHTML = `<p class="message">${error.message}</p>`;
  }
}

function renderList() {
  const config = resources[currentResource];
  const filtered = filteredRows();
  list.innerHTML = filtered.map((row) => `
    <button class="record ${currentRecord?.id === row.id ? "active" : ""}" type="button" data-id="${row.id}">
      <strong>${escapeHtml(recordTitle(row, config))}</strong>
      <span>${escapeHtml(recordSubtitle(row, config))}</span>
    </button>
  `).join("") || "<p>No hay registros.</p>";
  list.querySelectorAll("[data-id]").forEach((button) => {
    button.addEventListener("click", () => editRecord(rows.find((row) => String(row.id) === button.dataset.id)));
  });
}

function editRecord(record) {
  currentRecord = record || {};
  const config = resources[currentResource];
  $("[data-form-title]").textContent = config.readOnly ? "Detalle de auditoría" : (currentRecord?.id ? "Editar registro" : "Nuevo registro");
  $("[data-record-id]").textContent = currentRecord?.id ? `ID ${currentRecord.id}` : "";
  fields.innerHTML = config.readOnly
    ? config.fields.map(([name, label]) => renderReadOnlyField(name, label, currentRecord?.[name])).join("")
    : config.fields.map(([name, label, type, options]) => renderField(name, label, type, options, currentRecord?.[name])).join("");

  const titleField = fields.querySelector("[name='title'], [name='name']");
  const slugField = fields.querySelector("[name='slug']");
  if (titleField && slugField && !currentRecord?.id) {
    titleField.addEventListener("input", () => {
      if (!slugField.value) slugField.value = slugify(titleField.value);
    });
  }
  renderList();
}

function renderReadOnlyField(name, label, value) {
  const wide = ["details", "user_agent", "entity_title"].includes(name);
  return `
    <div class="readonly-field ${wide ? "field-wide" : ""}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(formatAuditValue(name, value)) || "Sin dato"}</strong>
    </div>
  `;
}

function renderField(name, label, type, options, value) {
  const wide = ["summary", "body", "requirements", "steps", "description", "biography", "bio", "internal_notes"].includes(name);
  if (type === "textarea") {
    return `<label class="${wide ? "field-wide" : ""}">${label}<textarea name="${name}">${escapeHtml(value || "")}</textarea></label>`;
  }
  if (type === "select") {
    return `<label>${label}<select name="${name}">${options.map((option) => `
      <option value="${option}" ${String(value || "") === option ? "selected" : ""}>${option}</option>
    `).join("")}</select></label>`;
  }
  return `<label class="${wide ? "field-wide" : ""}">${label}<input name="${name}" type="${type}" value="${escapeHtml(value ?? "")}"></label>`;
}

async function onSave(event) {
  event.preventDefault();
  if (resources[currentResource].readOnly) return;
  const message = $("[data-editor-message]");
  message.textContent = "Guardando...";
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    const endpoint = currentRecord?.id ? `/api/${currentResource}/${currentRecord.id}` : `/api/${currentResource}`;
    const data = await api(endpoint, {
      method: currentRecord?.id ? "PATCH" : "POST",
      body: payload,
    });
    message.textContent = "Guardado correctamente.";
    await loadRows();
    if (data.row?.id) editRecord(data.row);
  } catch (error) {
    message.textContent = error.message;
  }
}

function syncResourceUi(config) {
  $("[data-upload-box]").hidden = !config.upload || config.readOnly;
  $("[data-new]").hidden = Boolean(config.readOnly);
  $("[data-form-actions]").hidden = Boolean(config.readOnly);
  exportButton.hidden = !config.readOnly;
  auditFilters.hidden = currentResource !== "audit_logs";
  $("[data-filter]").placeholder = config.readOnly ? "Buscar dentro del resultado" : "Filtrar registros";
  $("[data-editor-message]").textContent = "";
}

function resourceQuery() {
  if (currentResource !== "audit_logs") return "";
  const params = new URLSearchParams({ limit: "200" });
  const dateFrom = $("[data-audit-date-from]").value;
  const dateTo = $("[data-audit-date-to]").value;
  const action = $("[data-audit-action]").value;
  const entity = $("[data-audit-entity]").value;
  const user = $("[data-audit-user]").value.trim();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (action) params.set("action", action);
  if (entity) params.set("entity_type", entity);
  if (user) params.set("user_email", user);
  return `?${params.toString()}`;
}

function filteredRows() {
  const term = normalize($("[data-filter]").value || "");
  return rows.filter((row) => normalize(JSON.stringify(row)).includes(term));
}

function recordTitle(row, config) {
  if (currentResource === "audit_logs") {
    return `${actionLabel(row.action)} · ${row.entity_title || row.entity_type || "Registro"}`;
  }
  return row[config.title] || row.key || "Sin título";
}

function recordSubtitle(row, config) {
  if (currentResource === "audit_logs") {
    return `${formatAuditValue("created_at", row.created_at)} · ${row.user_email || "Usuario no registrado"}`;
  }
  return row[config.subtitle] || row.status || row.created_at || "";
}

function exportRows() {
  const config = resources[currentResource];
  const exportFields = config.exportFields || config.fields.map(([name, label]) => [name, label]);
  const csvRows = [
    exportFields.map(([, label]) => csvCell(label)).join(","),
    ...filteredRows().map((row) => exportFields
      .map(([name]) => csvCell(formatAuditValue(name, row[name])))
      .join(",")),
  ];
  const blob = new Blob([`\ufeff${csvRows.join("\n")}`], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `auditoria-marcala-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function csvCell(value) {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

function actionLabel(value) {
  return {
    login: "Inicio de sesión",
    create: "Creación",
    update: "Actualización",
    upload: "Carga de archivo",
  }[value] || value || "Acción";
}

function formatAuditValue(name, value) {
  if (value == null || value === "") return "";
  if (name === "action") return actionLabel(value);
  if (name === "created_at") {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString("es-HN");
  }
  return value;
}

function debounce(callback, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...args), wait);
  };
}

async function uploadFile() {
  const input = $("[data-upload-file]");
  const folder = $("[data-upload-folder]").value;
  const message = $("[data-upload-message]");
  if (!input.files[0]) {
    message.textContent = "Selecciona un archivo.";
    return;
  }
  message.textContent = "Subiendo...";
  const form = new FormData();
  form.append("file", input.files[0]);
  form.append("folder", folder);
  try {
    const data = await api("/api/upload", { method: "POST", form });
    navigator.clipboard?.writeText(data.file_path);
    message.textContent = `Ruta copiada: ${data.file_path}`;
  } catch (error) {
    message.textContent = error.message;
  }
}

async function api(path, options = {}) {
  const headers = {};
  if (!options.public) headers.authorization = `Bearer ${localStorage.getItem(TOKEN_KEY) || ""}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  let body;
  if (options.form) {
    body = options.form;
  } else if (options.body) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  let response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers,
      body,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw new Error("La solicitud tardó demasiado. Revisa la conexión o el despliegue.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text };
  }
  if (!response.ok) throw new Error(data.error || data.detail || data.message || `Error HTTP ${response.status}`);
  return data;
}

function setActiveTab() {
  tabs.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === currentResource);
  });
}

function normalize(value) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function slugify(value) {
  return normalize(value).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 90);
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
