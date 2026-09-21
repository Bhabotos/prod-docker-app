// All API calls are same-origin (/api/...): nginx routes /api to FastAPI, so the
// browser never needs CORS or a hard-coded host. Text is inserted with
// textContent (never innerHTML) so item data can't inject markup.
const api = (path, options) => fetch(`/api${path}`, options);

const $ = (id) => document.getElementById(id);
const showError = (msg) => { $("error").textContent = msg; $("error").hidden = !msg; };

async function checkHealth() {
  try {
    const r = await api("/health");
    $("status").textContent = r.ok ? "ok" : `error ${r.status}`;
  } catch {
    $("status").textContent = "unreachable";
  }
}

async function loadItems() {
  const r = await api("/items");
  if (!r.ok) throw new Error(`Could not load items (${r.status})`);
  const list = $("items");
  list.replaceChildren();
  for (const item of await r.json()) {
    const li = document.createElement("li");
    const text = document.createElement("div");
    text.textContent = item.name;
    if (item.description) {
      const small = document.createElement("small");
      small.textContent = item.description;
      text.append(small);
    }
    const del = document.createElement("button");
    del.textContent = "Delete";
    del.addEventListener("click", () => run(async () => {
      await api(`/items/${item.id}`, { method: "DELETE" });
    }));
    li.append(text, del);
    list.append(li);
  }
}

async function run(action) {
  try { showError(""); await action(); await loadItems(); }
  catch (e) { showError(e.message); }
}

$("add-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  run(async () => {
    const body = { name: $("name").value.trim(), description: $("description").value.trim() || null };
    const r = await api("/items", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`Could not add item (${r.status})`);
    ev.target.reset();
  });
});

checkHealth();
run(async () => {});
