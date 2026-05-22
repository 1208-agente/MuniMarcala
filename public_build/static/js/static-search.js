const normalize = (value) => (value || "")
  .toLowerCase()
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .replace(/[^a-z0-9\s]/g, " ");

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
