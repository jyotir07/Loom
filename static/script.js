const API_BASE = "/models_catelog";

const providerEl = document.getElementById("provider");
const modalityEl = document.getElementById("modality");
const modelEl = document.getElementById("model");
const modelDropdownEl = document.getElementById("model-dropdown");
const modelTriggerEl = document.getElementById("model-trigger");
const modelTriggerLabelEl = document.getElementById("model-trigger-label");
const modelMenuEl = document.getElementById("model-menu");
const promptEl = document.getElementById("prompt");
const runBtn = document.getElementById("run");
const statusEl = document.getElementById("status");
const outputEl = document.getElementById("output");
const codeContentEl = document.getElementById("code-content");
const codeFilenameEl = document.getElementById("code-filename");

let catalog = {};
let currentModelModality = null;

async function loadCatalog() {
  const res = await fetch(`${API_BASE}/api/catalog`);
  catalog = await res.json();
  refreshProviderOptions();
  refreshModels();
}

function providersForModality(modality) {
  if (modality === "all") return Object.keys(catalog);
  return Object.entries(catalog)
    .filter(([, data]) => (data.modalities?.[modality] || []).length > 0)
    .map(([id]) => id);
}

function refreshProviderOptions() {
  const modality = modalityEl.value;
  const previous = providerEl.value;
  const allowed = providersForModality(modality);
  providerEl.innerHTML = "";
  for (const id of allowed) {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = catalog[id].label;
    providerEl.appendChild(opt);
  }
  if (allowed.includes(previous)) {
    providerEl.value = previous;
  }
}

function formatInr(value) {
  return `₹${value.toFixed(2)}`;
}

function formatInrCompact(value) {
  if (value >= 100) return `₹${Math.round(value)}`;
  return `₹${value.toFixed(2)}`;
}

function badgeFor(m) {
  if (typeof m.cost_inr === "number") {
    return { text: formatInr(m.cost_inr), cls: "cost-badge" };
  }
  if (typeof m.input_inr_per_1m === "number") {
    const inTxt = formatInrCompact(m.input_inr_per_1m);
    const outTxt = typeof m.output_inr_per_1m === "number"
      ? formatInrCompact(m.output_inr_per_1m)
      : null;
    const text = outTxt ? `${inTxt} / ${outTxt} per 1M` : `${inTxt} per 1M`;
    return { text, cls: "cost-badge" };
  }
  if (m.free) {
    return { text: "free", cls: "free-badge" };
  }
  return null;
}

function setTriggerContent(name, badge) {
  modelTriggerLabelEl.innerHTML = "";
  const nameSpan = document.createElement("span");
  nameSpan.className = "model-name";
  nameSpan.textContent = name;
  modelTriggerLabelEl.appendChild(nameSpan);
  if (badge) {
    const el = document.createElement("span");
    el.className = badge.cls;
    el.textContent = badge.text;
    modelTriggerLabelEl.appendChild(el);
  }
}

function selectModel(m) {
  modelEl.value = m.id;
  currentModelModality = m._modality || modalityEl.value;
  setTriggerContent(m.name, badgeFor(m));
  closeMenu();
  refreshCode();
}

function activeModality() {
  return modalityEl.value === "all" ? currentModelModality : modalityEl.value;
}

let codeRequestId = 0;

async function refreshCode() {
  const provider = providerEl.value;
  const modality = activeModality();
  if (!provider || !modality) return;

  const reqId = ++codeRequestId;
  codeContentEl.textContent = "Loading…";
  codeFilenameEl.textContent = "";

  try {
    const res = await fetch(
      `${API_BASE}/api/code?provider=${encodeURIComponent(provider)}&modality=${encodeURIComponent(modality)}`
    );
    const data = await res.json();
    if (reqId !== codeRequestId) return;
    if (!res.ok) {
      codeContentEl.textContent = data.error || `Request failed (${res.status})`;
      return;
    }
    codeContentEl.textContent = data.code || "(no source)";
    codeFilenameEl.textContent = data.filename || "";
  } catch (err) {
    if (reqId !== codeRequestId) return;
    codeContentEl.textContent = err.message || String(err);
  }
}

function openMenu() {
  modelMenuEl.hidden = false;
  modelTriggerEl.setAttribute("aria-expanded", "true");
  modelDropdownEl.classList.add("open");
}

function closeMenu() {
  modelMenuEl.hidden = true;
  modelTriggerEl.setAttribute("aria-expanded", "false");
  modelDropdownEl.classList.remove("open");
}

function collectModels(provider, modality) {
  const data = catalog[provider];
  if (!data) return [];
  if (modality === "all") {
    const out = [];
    for (const [mod, list] of Object.entries(data.modalities || {})) {
      for (const m of list) out.push({ ...m, _modality: mod });
    }
    return out;
  }
  return data.modalities?.[modality] || [];
}

function refreshModels() {
  const provider = providerEl.value;
  const modality = modalityEl.value;
  const models = collectModels(provider, modality);
  modelEl.innerHTML = "";
  modelMenuEl.innerHTML = "";
  closeMenu();

  if (!provider || models.length === 0) {
    const emptyMsg = provider
      ? `No ${modality} models for ${catalog[provider]?.label || provider}`
      : "No providers available";
    const opt = document.createElement("option");
    opt.textContent = emptyMsg;
    opt.disabled = true;
    modelEl.appendChild(opt);

    modelTriggerLabelEl.textContent = emptyMsg;
    modelTriggerEl.disabled = true;
    runBtn.disabled = true;
    refreshCode();
    return;
  }

  modelTriggerEl.disabled = false;
  for (const m of models) {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.name;
    modelEl.appendChild(opt);

    const li = document.createElement("li");
    li.className = "dropdown-item";
    li.setAttribute("role", "option");
    li.dataset.id = m.id;

    const nameSpan = document.createElement("span");
    nameSpan.className = "model-name";
    nameSpan.textContent = m.name;
    li.appendChild(nameSpan);

    if (modality === "all" && m._modality) {
      const typeTag = document.createElement("span");
      typeTag.className = "type-tag";
      typeTag.textContent = m._modality;
      li.appendChild(typeTag);
    }

    const badge = badgeFor(m);
    if (badge) {
      const el = document.createElement("span");
      el.className = badge.cls;
      el.textContent = badge.text;
      li.appendChild(el);
    }

    li.addEventListener("click", () => selectModel(m));
    modelMenuEl.appendChild(li);
  }

  selectModel(models[0]);
  runBtn.disabled = false;
}

function setStatus(message, isError = false) {
  statusEl.textContent = message || "";
  statusEl.classList.toggle("error", Boolean(isError));
}

function showOutput(result) {
  outputEl.hidden = false;
  outputEl.innerHTML = "";

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${catalog[providerEl.value].label} · ${modelEl.options[modelEl.selectedIndex].textContent}`;
  outputEl.appendChild(meta);

  if (result.kind === "text") {
    const pre = document.createElement("div");
    pre.textContent = result.text || "(empty response)";
    outputEl.appendChild(pre);
    return;
  }

  if (result.kind === "image") {
    if (result.text) {
      const caption = document.createElement("div");
      caption.textContent = result.text;
      outputEl.appendChild(caption);
    }
    for (const img of result.images || []) {
      const el = document.createElement("img");
      if (img.data_b64) {
        el.src = `data:${img.mime_type || "image/png"};base64,${img.data_b64}`;
      } else if (img.url) {
        el.src = img.url;
      }
      el.alt = "generated image";
      outputEl.appendChild(el);
    }
    return;
  }

  if (result.kind === "video") {
    if (result.text) {
      const caption = document.createElement("div");
      caption.textContent = result.text;
      outputEl.appendChild(caption);
    }
    for (const vid of result.videos || []) {
      const el = document.createElement("video");
      el.controls = true;
      el.preload = "metadata";
      if (vid.data_b64) {
        el.src = `data:${vid.mime_type || "video/mp4"};base64,${vid.data_b64}`;
      } else if (vid.url) {
        el.src = vid.url;
      }
      outputEl.appendChild(el);
    }
    return;
  }

  outputEl.textContent = JSON.stringify(result, null, 2);
}

async function generate() {
  const prompt = promptEl.value.trim();
  if (!prompt) {
    setStatus("Enter a prompt first.", true);
    return;
  }
  const modality = activeModality();
  runBtn.disabled = true;
  setStatus(modality === "video"
    ? "Generating video (this can take 1–3 minutes)..."
    : "Generating...");
  outputEl.hidden = true;

  try {
    const res = await fetch(`${API_BASE}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: providerEl.value,
        modality,
        model: modelEl.value,
        prompt,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    setStatus("Done.");
    showOutput(data);
  } catch (err) {
    setStatus(err.message || String(err), true);
  } finally {
    runBtn.disabled = false;
  }
}

providerEl.addEventListener("change", refreshModels);
modalityEl.addEventListener("change", () => {
  refreshProviderOptions();
  refreshModels();
});
runBtn.addEventListener("click", generate);

modelTriggerEl.addEventListener("click", (e) => {
  e.stopPropagation();
  if (modelTriggerEl.disabled) return;
  if (modelMenuEl.hidden) openMenu();
  else closeMenu();
});

document.addEventListener("click", (e) => {
  if (!modelDropdownEl.contains(e.target)) closeMenu();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeMenu();
});

loadCatalog().catch((err) => setStatus(`Failed to load catalog: ${err.message}`, true));

// ---------- Add-model modal ----------

const addModelBtn = document.getElementById("add-model-btn");
const addModelModal = document.getElementById("add-model-modal");
const addModelForm = document.getElementById("add-model-form");
const amStatus = document.getElementById("am-status");
const amSubmit = document.getElementById("am-submit");

function openAddModelModal() {
  addModelModal.hidden = false;
  amStatus.textContent = "";
  amStatus.classList.remove("error");
  document.getElementById("am-provider-key").focus();
}

function closeAddModelModal() {
  addModelModal.hidden = true;
  addModelForm.reset();
  amSubmit.disabled = false;
}

addModelBtn?.addEventListener("click", openAddModelModal);

addModelModal?.querySelectorAll("[data-close-modal]").forEach((el) => {
  el.addEventListener("click", closeAddModelModal);
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && addModelModal && !addModelModal.hidden) {
    closeAddModelModal();
  }
});

function setAmStatus(msg, isError = false) {
  amStatus.textContent = msg || "";
  amStatus.classList.toggle("error", Boolean(isError));
}

// Auto-retry add-model submits when the network call fails mid-flight.
// Cause: Flask's debug auto-reloader restarts the moment we write a new
// provider .py + patch __init__.py, which kills the in-flight HTTP
// connection. By the time we retry, the server is back up, the DB + catalog
// + init are already updated, and the retry returns success immediately.
//
// Only retries on TypeError (network failure). HTTP error responses (4xx/5xx)
// are real backend errors and are surfaced to the user as-is.
async function postAddModelWithRetry(payload, maxAttempts = 4) {
  const backoffMs = [0, 1500, 2500, 4000];
  let lastErr;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (attempt > 0) {
      setAmStatus(`Server is reloading, retrying… (${attempt}/${maxAttempts - 1})`);
      await new Promise((r) => setTimeout(r, backoffMs[attempt]));
    }
    try {
      const res = await fetch(`${API_BASE}/api/models/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      return { res, data };
    } catch (err) {
      lastErr = err;
      // TypeError  -> network drop (connection killed mid-request).
      // SyntaxError -> partial body (connection killed mid-response).
      if (!(err instanceof TypeError) && !(err instanceof SyntaxError)) throw err;
    }
  }
  throw lastErr;
}

addModelForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  amSubmit.disabled = true;

  const payload = {
    provider_key: document.getElementById("am-provider-key").value.trim().toLowerCase(),
    provider_label: document.getElementById("am-provider-label").value.trim(),
    model_id: document.getElementById("am-model-id").value.trim(),
    model_name: document.getElementById("am-model-name").value.trim(),
    modality: document.getElementById("am-modality").value,
  };

  setAmStatus("Updating DB…");

  try {
    const { res, data } = await postAddModelWithRetry(payload);
    if (!res.ok) {
      const stage = data.stage ? `[${data.stage}] ` : "";
      throw new Error(stage + (data.error || `Request failed (${res.status})`));
    }

    let msg = "Done.";
    if (data.created_file) {
      msg = `Done. Wrote ${data.created_file}. Flask is reloading…`;
    } else if (data.catalog === "existed") {
      msg = "Already present — nothing to do.";
    } else {
      msg = "Done. Refreshing dropdowns…";
    }
    setAmStatus(msg);

    await loadCatalog();
    // Auto-select the newly added provider for convenience.
    if (catalog[payload.provider_key]) {
      modalityEl.value = payload.modality;
      refreshProviderOptions();
      providerEl.value = payload.provider_key;
      refreshModels();
    }

    setTimeout(closeAddModelModal, data.created_file ? 1500 : 700);
  } catch (err) {
    setAmStatus(err.message || String(err), true);
    amSubmit.disabled = false;
  }
});
