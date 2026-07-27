const $ = (q, p = document) => p.querySelector(q);
const $$ = (q, p = document) => [...p.querySelectorAll(q)];

const main = $("#main");
const toastBox = $("#toast");
const themeBtn = $("#theme");
const themeMeta = $("meta[name='theme-color']");
const api = $("meta[name='api-base']")?.content.replace(/\/$/, "") || "";
// const api = ($("meta[name='api-base']")?.content || "http://localhost:8000").replace(/\/$/, "");

const pages = ["home", "upload", "review", "records"];
const moneyFields = [
  "subtotal",
  "tax",
  "discount",
  "additional_charges",
  "total",
];
const fields = [
  "vendor",
  "invoice_number",
  "date",
  "currency",
  "subtotal",
  "tax",
  "discount",
  "additional_charges",
  "total",
];
const statusNames = {
  auto_approved: ["ok", "Auto Approved"],
  approved: ["ok", "Approved"],
  pending_review: ["pending", "Pending Review"],
  blocked: ["bad", "Blocked"],
  rejected: ["bad", "Rejected"],
  error: ["bad", "Failed"],
};
const maxFiles = 25;
const gap = 900;

const app = {
  page: read("ll-page", "home"),
  theme: read("ll-theme", ""),
  open: read("ll-open", ""),
  files: [],
  urls: [],
  turn: 0,
  timer: 0,
};

let cache = {};

function read(name, value = "") {
  try {
    return sessionStorage.getItem(name) ?? localStorage.getItem(name) ?? value;
  } catch {
    return value;
  }
}

function save(name, value, local = false) {
  try {
    (local ? localStorage : sessionStorage).setItem(name, value);
  } catch {}
}

function show(id, area = main) {
  area.innerHTML = $("#" + id).innerHTML;
}

function same(page, turn) {
  return app.page === page && app.turn === turn;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function title(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (x) => x.toUpperCase());
}

function num(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";

  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function cost(value, digits = 5) {
  const n = Number(value);
  return Number.isFinite(n) ? `$${n.toFixed(digits)}` : "$0.00000";
}

function plural(n) {
  return n === 1 ? "" : "s";
}

function wait(ms) {
  return new Promise((done) => setTimeout(done, ms));
}

function csvText(rows) {
  const all = [
    [
      "filename",
      "doc_id",
      "status",
      "vendor",
      "total",
      "currency",
      "held_fields",
      "cost_usd",
    ],
  ];

  rows.forEach((row) => {
    all.push([
      row.name,
      row.doc_id,
      row.status,
      row.vendor,
      row.totalRaw,
      row.currency,
      row.flagged,
      row.costRaw,
    ]);
  });

  return all
    .map((row) =>
      row
        .map((cell) => {
          const text = String(cell ?? "");
          return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
        })
        .join(","),
    )
    .join("\n");
}

function download(text, name) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function join(path) {
  path = String(path);
  if (/^https?:\/\//i.test(path)) return path;
  return api + (path.startsWith("/") ? "" : "/") + path;
}

async function get(path, fresh = false) {
  const old = cache[path];

  if (!fresh && old && Date.now() - old.time < 5000) {
    return old.data;
  }

  const res = await fetch(join(path), {
    headers: { Accept: "application/json" },
  });

  if (!res.ok) throw new Error(await message(res));

  const data = await res.json();
  cache[path] = { time: Date.now(), data };
  return data;
}

async function send(path, body) {
  const res = await fetch(join(path), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(await message(res));

  try {
    return await res.json();
  } catch {
    return {};
  }
}

async function message(res) {
  try {
    const data = await res.clone().json();

    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail?.message) return data.detail.message;
    if (data?.message) return data.message;
    return JSON.stringify(data);
  } catch {
    return (await res.text()) || `Request failed (${res.status})`;
  }
}

function clearCache() {
  cache = {};
}

function toast(text) {
  clearTimeout(app.timer);
  toastBox.textContent = text;
  toastBox.classList.add("show");

  app.timer = setTimeout(() => {
    toastBox.classList.remove("show");
  }, 2600);
}

function setTheme(value, store = true) {
  const dark = value === "dark";

  app.theme = dark ? "dark" : "light";
  document.documentElement.dataset.theme = app.theme;
  $("span", themeBtn).innerHTML = dark ? "&#9789;" : "&#9788;";

  themeBtn.title = dark ? "Switch to light mode" : "Switch to dark mode";
  themeBtn.setAttribute("aria-label", themeBtn.title);
  themeMeta?.setAttribute("content", dark ? "#181818" : "#f5f5f5");

  if (store) save("ll-theme", app.theme, true);
}

function markPage() {
  $$(".nav-btn").forEach((btn) => {
    const active = btn.dataset.page === app.page;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-current", active ? "page" : "false");
  });
}

function go(page, focus = true) {
  app.page = pages.includes(page) ? page : "home";
  app.turn += 1;

  save("ll-page", app.page);
  markPage();
  draw(app.page);

  if (focus) {
    window.scrollTo({ top: 0, behavior: "auto" });
    requestAnimationFrame(() => main.focus({ preventScroll: true }));
  }
}

function draw(page) {
  if (page === "home") home();
  if (page === "upload") upload();
  if (page === "review") review();
  if (page === "records") records();
}

function pill(value) {
  const x = Number(value);
  const n = Number.isFinite(x) ? x : 0;
  const type = n >= 0.9 ? "hi" : n >= 0.75 ? "mid" : "lo";
  return `<span class="ll-pill ${type}">${n.toFixed(2)}</span>`;
}

function chip(value) {
  const item = statusNames[value] || ["pending", String(value || "pending")];
  return `<span class="ll-status ${item[0]}">${esc(item[1])}</span>`;
}

function field(label, value, confidence = null, money = false) {
  const shown = value === "" || value == null ? "-" : esc(value);
  const moneyClass = money && shown !== "-" ? " money" : "";
  const score = confidence == null ? "" : pill(confidence);
  return `
    <div class="ll-field">
      <div class="ll-field-label">
        <span>${esc(label)}</span>
        ${score}
      </div>
      <div class="ll-field-value${moneyClass}" title="${shown}">
        ${shown}
      </div>
    </div>`;
}

function grid(data = {}) {
  const cards = fields
    .map((name, i) => {
      const item = data[name] || { value: null, confidence: 0 };
      return field(
        title(name),
        item?.value,
        item?.confidence,
        moneyFields.includes(name),
      );
    })
    .join("");

  const items = Array.isArray(data.line_items) ? data.line_items : [];
  let table = "";

  if (items.length) {
    const rows = items
      .map(
        (item) => `
      <tr>
        <td>${esc(item?.description ?? "")}</td>
        <td class="num">${num(item?.quantity, 0)}</td>
        <td class="num">${num(item?.unit_price)}</td>
        <td class="num money">${num(item?.amount)}</td>
        <td class="num">${pill(item?.confidence)}</td>
      </tr>`,
      )
      .join("");

    table = `
      <div class="ll-rule">Line items</div>
      <div class="ll-table-wrap">
        <table class="ll-table">
          <thead>
            <tr>
              <th>Description</th>
              <th>Qty</th>
              <th>Unit price</th>
              <th>Amount</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  return `<div class="ll-field-grid">${cards}</div>${table}`;
}

function flags(list = []) {
  if (!Array.isArray(list) || !list.length) return "";

  const rows = list
    .map(
      (item) => `
    <tr>
      <td>${esc(item?.field_path ?? "")}</td>
      <td class="num">${esc(item?.value ?? "")}</td>
      <td class="num">${pill(item?.confidence)}</td>
      <td>${esc(item.reason)}</td>
    </tr>`,
    )
    .join("");

  return `
    <div class="ll-rule">Held for review</div>
    <div class="ll-table-wrap">
      <table class="ll-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Extracted value</th>
            <th>Confidence</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function banner(type, html) {
  return `<div class="ll-banner ${type}">${html}</div>`;
}

async function home() {
  const turn = app.turn;
  show("home-page");

  try {
    const docs = await get("/documents");
    if (!same("home", turn)) return;

    $("[data-x='all']", main).textContent = docs.length;
    $("[data-x='ok']", main).textContent = docs.filter((item) =>
      ["auto_approved", "approved"].includes(item?.status),
    ).length;
    $("[data-x='wait']", main).textContent = docs.filter(
      (item) => item?.status === "pending_review",
    ).length;
  } catch {}
}

function upload() {
  show("upload-page");

  app.urls.forEach((url) => URL.revokeObjectURL(url));
  app.urls = [];

  const files = app.files;
  const input = $("#file", main);
  const drop = $("#drop", main);
  const run = $("#run", main);

  if (files.length) {
    const kb = files.reduce((total, file) => total + file.size, 0) / 1024;
    const thumbs = files
      .map((file, i) => {
        const url = URL.createObjectURL(file);
        app.urls.push(url);

        return `
        <figure class="batch-thumb">
          <img src="${esc(url)}" alt="${esc(file.name)}">
          <button
            class="batch-drop"
            type="button"
            data-drop="${i}"
            aria-label="Remove ${esc(file.name)}"
          >x</button>
          <figcaption>${esc(file.name)}</figcaption>
        </figure>`;
      })
      .join("");

    $("#preview", main).innerHTML = `
      <div class="preview-card">
        <div class="batch-strip">${thumbs}</div>
        <div class="ll-file-meta">
          <span>${files.length} file${plural(files.length)} ready</span>
          <span>${Math.round(kb).toLocaleString()} KB total</span>
        </div>
      </div>`;

    run.disabled = false;
    run.textContent = `Extract ${files.length} document${plural(files.length)}`;

    const seconds = Math.round((files.length * (12000 + gap)) / 1000);
    $("#upload-note", main).textContent =
      `Files are read one at a time. About ${timeLeft(seconds)} for ` +
      `${files.length} file${plural(files.length)}.`;
  }

  input.addEventListener("change", () => {
    pick(input.files);
    input.value = "";
  });

  drop.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("drag");
  });

  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));

  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
    pick(e.dataTransfer?.files);
  });

  $$("[data-drop]", main).forEach((btn) => {
    btn.addEventListener("click", () => {
      app.files.splice(Number(btn.dataset.drop), 1);
      upload();
    });
  });

  run.addEventListener("click", ingest);
}

function pick(list) {
  const files = [...(list || [])];
  if (!files.length) return;

  const good = files.filter(
    (file) =>
      ["image/jpeg", "image/png"].includes(file.type) ||
      /\.(jpe?g|png)$/i.test(file.name),
  );

  if (!good.length) {
    toast("Choose JPG or PNG files.");
    return;
  }

  const room = Math.max(maxFiles - app.files.length, 0);
  const added = good.slice(0, room);
  const skipped = files.length - good.length;

  app.files = app.files.concat(added);

  if (skipped) {
    toast(`${skipped} file${plural(skipped)} skipped. JPG or PNG only.`);
  } else if (added.length < good.length) {
    toast(`Limit is ${maxFiles} files per batch.`);
  }

  upload();
}

async function ingestOne(file, attempt = 0) {
  const out = {
    name: file.name,
    doc_id: "",
    status: "error",
    vendor: "",
    currency: "",
    total: "-",
    totalRaw: "",
    flagged: 0,
    costRaw: 0,
    detail: "",
    extraction: null,
    held: [],
    img: "",
  };

  const body = new FormData();
  body.append("file", file, file.name);

  let res;

  try {
    res = await fetch(join("/ingest"), {
      method: "POST",
      headers: { Accept: "application/json" },
      body,
    });
  } catch (e) {
    out.detail = `API unreachable: ${e.message}`;
    return out;
  }

  if (res.status === 429 && attempt < 3) {
    await wait(3000 * (attempt + 1));
    return ingestOne(file, attempt + 1);
  }

  if (res.status === 422) {
    out.status = "blocked";

    try {
      const data = await res.json();
      out.doc_id = String(data?.detail?.doc_id ?? "");
      out.detail =
        data?.detail?.blocked_reason || "Blocked by the moderation gate.";
    } catch {
      out.detail = "Blocked by the moderation gate.";
    }

    return out;
  }

  if (!res.ok) {
    out.detail = await message(res);
    return out;
  }

  let data;

  try {
    data = await res.json();
  } catch {
    out.detail = "The API returned an unreadable response.";
    return out;
  }

  const extraction = data.extraction || {};
  const total = Number(extraction?.total?.value);

  out.doc_id = String(data.doc_id ?? "");
  out.status = String(data.status ?? "");
  out.vendor = String(extraction?.vendor?.value ?? "");
  out.currency = String(extraction?.currency?.value ?? "");
  out.totalRaw = Number.isFinite(total) ? total : "";
  out.total = Number.isFinite(total) ? num(total) : "-";
  out.flagged = Array.isArray(data.flagged_fields)
    ? data.flagged_fields.length
    : 0;
  out.costRaw = Number(data.cost_usd) || 0;
  out.extraction = extraction;
  out.held = Array.isArray(data.flagged_fields) ? data.flagged_fields : [];
  out.img = String(data.watermarked_image_url || "");

  return out;
}

function batchRow(row, i) {
  const canOpen = Boolean(row.extraction) || Boolean(row.detail);
  const image = row.img
    ? `
    <img
      class="ll-doc-img"
      src="${esc(join(row.img))}"
      alt="Processed document ${esc(row.doc_id)}"
    >
    <p class="caption">
      The document id and UTC time are shown in the lower right.
    </p>`
    : "";

  const detail = row.extraction
    ? `
    <div class="batch-detail-grid">
      <div>${image}</div>
      <div>${grid(row.extraction)}${flags(row.held)}</div>
    </div>`
    : banner("bad", esc(row.detail || "No details available."));

  return `
    <tr>
      <td>
        ${esc(row.name)}
        ${row.doc_id ? `<br><span class="batch-why">${esc(row.doc_id)}</span>` : ""}
      </td>
      <td>${chip(row.status)}</td>
      <td>${esc(row.vendor || "-")}</td>
      <td class="num money">${esc(row.total)}</td>
      <td class="num">${row.flagged || "-"}</td>
      <td class="num">${cost(row.costRaw)}</td>
      <td class="num">
        ${
          canOpen
            ? `
          <button
            class="batch-more"
            type="button"
            data-more="${i}"
            aria-expanded="false"
            aria-label="Show details for ${esc(row.name)}"
          >&#9656;</button>`
            : ""
        }
      </td>
    </tr>
    <tr class="batch-detail" data-row="${i}" hidden>
      <td colspan="7">
        <div class="batch-detail-in">${detail}</div>
      </td>
    </tr>`;
}

async function ingest() {
  const files = app.files.slice();
  if (!files.length) return;

  const turn = app.turn;
  const run = $("#run", main);
  const result = $("#result", main);

  run.disabled = true;
  show("batch-results", result);

  const bar = $("#pbar", main);
  const text = $("#ptext", main);
  const rows = $("#brows", main);
  const done = [];
  const started = Date.now();

  rows.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-more]");
    if (!btn) return;

    const panel = $(`.batch-detail[data-row="${btn.dataset.more}"]`, rows);
    if (!panel) return;

    const open = panel.hasAttribute("hidden");
    panel.toggleAttribute("hidden", !open);
    btn.setAttribute("aria-expanded", String(open));
    btn.classList.toggle("open", open);
  });

  for (let i = 0; i < files.length; i += 1) {
    if (!same("upload", turn)) return;

    const average = i ? (Date.now() - started) / i : 0;
    const left = average
      ? Math.round((average * (files.length - i)) / 1000)
      : 0;

    text.textContent =
      `Reading ${i + 1} of ${files.length}: ${files[i].name}` +
      (left ? ` · about ${timeLeft(left)} remaining` : "");
    bar.style.width = `${Math.round((i / files.length) * 100)}%`;

    const row = await ingestOne(files[i]);
    if (!same("upload", turn)) return;

    done.push(row);
    rows.insertAdjacentHTML("beforeend", batchRow(row, i));
    bar.style.width = `${Math.round(((i + 1) / files.length) * 100)}%`;

    if (i < files.length - 1) await wait(gap);
  }

  clearCache();

  const approved = done.filter((row) => row.status === "auto_approved").length;
  const reviewCount = done.filter(
    (row) => row.status === "pending_review",
  ).length;
  const failed = done.length - approved - reviewCount;
  const spend = done.reduce(
    (total, row) => total + (Number(row.costRaw) || 0),
    0,
  );

  text.textContent =
    `Done. ${approved} approved, ${reviewCount} sent to review, ` +
    `${failed} failed or blocked. Spend ${cost(spend)}.`;

  if (failed === 0) {
    app.files = [];
    app.urls.forEach((url) => URL.revokeObjectURL(url));
    app.urls = [];

    $("#preview", main).innerHTML = `
      <div class="ll-empty-preview">
        <div class="ll-empty-icon"></div>
        <b>No files selected</b>
        <p>Your receipts will appear here.</p>
      </div>`;

    run.textContent = "Extract documents";
    $("#upload-note", main).textContent = "Choose files to start.";
  }

  $("#bactions", main).innerHTML = `
    <button class="btn secondary small" type="button" id="csv">
      Download CSV summary
    </button>
    ${
      reviewCount
        ? `
      <button class="btn primary small" type="button" data-go="review">
        Open review queue
      </button>`
        : ""
    }`;

  $("#csv", main).addEventListener("click", () => {
    download(csvText(done), `recordslens-batch-${Date.now()}.csv`);
  });

  run.disabled = failed === 0;
}

async function review(fresh = false) {
  const turn = app.turn;
  show("review-page");

  $("#reload", main).addEventListener("click", () => review(true));

  let list;

  try {
    list = await get("/review", fresh);
  } catch (e) {
    if (same("review", turn)) {
      $("#review-box", main).innerHTML = banner(
        "bad",
        `<b>API unreachable.</b> ${esc(e.message)}`,
      );
    }
    return;
  }

  if (!same("review", turn)) return;

  const area = $("#review-box", main);

  if (!Array.isArray(list) || !list.length) {
    area.innerHTML = banner("ok", "No documents need review.");
    return;
  }

  const waiting = chip("pending_review").replace(
    "pending review",
    `${list.length} document${plural(list.length)} waiting`,
  );

  area.innerHTML = `
    <div class="review-count">${waiting}</div>
    <div class="review-list">
      ${list.map((item, i) => reviewItem(item, list.length === 1 && i === 0)).join("")}
    </div>`;

  $$('[data-do="reject"]', area).forEach((btn) => {
    btn.addEventListener("click", () => rejectOne(btn, list));
  });

  $$('[data-do="approve"]', area).forEach((btn) => {
    btn.addEventListener("click", () => approveOne(btn, list));
  });
}

function reviewItem(item, open) {
  const id = String(item?.doc_id ?? "");
  const held = Array.isArray(item?.flagged_fields) ? item.flagged_fields : [];

  const rows = held
    .map((field, i) => {
      const path = String(field?.field_path ?? "");
      const value = String(field?.value ?? "");
      const reason = String(
        field?.reason ?? "This field requires manual review.",
      );

      return `
      <div class="correction-row">
        <div class="ll-flag-info">
			<div class="ll-correction-label">${esc(title(path))}</div>

			<div class="ll-correction-value">
				${esc(value || "No value extracted")}
			</div>

			<div class="ll-flag-meta">
				<span>Confidence ${pill(field?.confidence)}</span>
			</div>

			<div class="ll-flag-reason">
				<strong>Why it was flagged</strong>
				<span>${esc(reason)}</span>
			</div>
		</div>

        <div>
          <label class="ll-correction-label" for="fix-${esc(id)}-${i}">
            Corrected value
          </label>
          <input
            class="text-input"
            id="fix-${esc(id)}-${i}"
            data-f="${esc(path)}"
            data-old="${esc(value)}"
            value="${esc(value)}"
          >
        </div>
      </div>`;
    })
    .join("");

  return `
    <details class="review-item" data-id="${esc(id)}" ${open ? "open" : ""}>
      <summary>
        ${esc(item?.filename ?? "")} |
        ${esc(id)} |
        ${held.length} field${plural(held.length)} held
      </summary>

      <div class="review-body">
        <div class="review-grid">
          <div>
            <img
              class="ll-doc-img"
              src="${esc(join(item?.watermarked_image_url || ""))}"
              alt="Watermarked document ${esc(id)}"
            >
          </div>
          <div>${grid(item?.extraction || {})}</div>
        </div>

        <div class="ll-rule">Fields requiring review</div>
        ${rows}

        <div class="form-row">
          <label for="reason-${esc(id)}">Reason, if rejecting</label>
          <input
            class="text-input"
            id="reason-${esc(id)}"
            data-reason
            value="Not a valid receipt/invoice"
          >
        </div>

        <div class="review-actions">
          <button class="btn primary" type="button" data-do="approve">Approve</button>
          <button class="btn secondary" type="button" data-do="reject">Reject</button>
          <span></span>
        </div>
      </div>
    </details>`;
}

function findReviewItem(btn, list) {
  const box = btn.closest(".review-item");
  const id = box?.dataset.id || "";
  const item = list.find((row) => String(row?.doc_id ?? "") === id);
  return [box, item];
}

function lock(box, value) {
  $$("button[data-do]", box).forEach((btn) => {
    btn.disabled = value;
  });
}

async function rejectOne(btn, list) {
  const [box, item] = findReviewItem(btn, list);
  if (!box || !item) return;

  lock(box, true);
  const reason =
    $("[data-reason]", box)?.value || "Not a valid receipt/invoice";

  try {
    await send("/reject", { doc_id: item.doc_id, reason });
    clearCache();
    toast("Rejected.");
    review(true);
  } catch (e) {
    toast(`Reject failed: ${e.message}`);
    lock(box, false);
  }
}

async function approveOne(btn, list) {
  const [box, item] = findReviewItem(btn, list);
  if (!box || !item) return;

  lock(box, true);

  const corrections = $$("input[data-f]", box)
    .filter((input) => input.value !== input.dataset.old)
    .map((input) => ({
      field_path: input.dataset.f,
      corrected_value: input.value,
    }));

  try {
    const data = await send("/approve", {
      doc_id: item.doc_id,
      corrections,
    });

    const count = Number(data?.applied_corrections) || 0;
    clearCache();
    toast(`Approved, ${count} correction${plural(count)}.`);
    review(true);
  } catch (e) {
    toast(`Approve failed: ${e.message}`);
    lock(box, false);
  }
}

async function records(fresh = false) {
  const turn = app.turn;
  show("records-page");

  let docs;

  try {
    docs = await get("/documents", fresh);
  } catch (e) {
    if (same("records", turn)) {
      $("#records-box", main).innerHTML = banner(
        "bad",
        `<b>API unreachable.</b> ${esc(e.message)}`,
      );
    }
    return;
  }

  if (!same("records", turn)) return;
  showRecords(Array.isArray(docs) ? docs : []);
}

function showRecords(docs) {
  const area = $("#records-box", main);

  if (!docs.length) {
    area.innerHTML = banner("pending", "No documents have been uploaded yet.");
    return;
  }

  show("records-list", area);

  const auto = docs.filter((item) => item?.status === "auto_approved").length;
  const approved = docs.filter((item) => item?.status === "approved").length;
  const reviewCount = docs.filter(
    (item) => item?.status === "pending_review",
  ).length;
  const bad = docs.filter((item) =>
    ["rejected", "blocked"].includes(item?.status),
  ).length;
  const total = docs.reduce(
    (sum, item) => sum + (Number(item?.cost_usd) || 0),
    0,
  );

  $("[data-total='auto']", area).textContent = auto;
  $("[data-total='approved']", area).textContent = approved;
  $("[data-total='review']", area).textContent = reviewCount;
  $("[data-total='bad']", area).textContent = bad;
  $("[data-total='cost']", area).textContent = `$${total.toFixed(4)}`;

  $(".records", area).insertAdjacentHTML(
    "beforeend",
    docs.map((item) => recordsRow(item)).join(""),
  );

  $$('[data-do="open"]', area).forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id || "";
      app.open = app.open === id ? "" : id;
      save("ll-open", app.open);
      showRecords(docs);
    });
  });
}

function recordsRow(item) {
  const id = String(item?.doc_id ?? "");
  const open = app.open === id;
  const total = Number(item?.total);
  const currency = String(
    item?.currency || item?.extraction?.currency?.value || "",
  ).toUpperCase();
  const shown = Number.isFinite(total)
    ? `${currency ? currency + " " : ""}${num(total)}`
    : "-";
  const time = String(item?.created_at ?? "")
    .slice(0, 16)
    .replace("T", " at ");

  return `
    <div class="records-row">
      <div class="ll-row-text">
        ${esc(item?.filename ?? "")}<br>
        <span class="mono">${esc(id)}</span>
      </div>

      <div>${chip(item?.status)}</div>
      <div class="ll-row-text">${esc(item?.vendor || "-")}</div>
      <div class="ll-money-cell">${shown}</div>
      <div class="ll-row-text"><span class="mono">${esc(time)}</span></div>

      <button
        class="btn ${open ? "primary" : "secondary"} small"
        type="button"
        data-do="open"
        data-id="${esc(id)}"
      >
        ${open ? "Hide" : "Details"}
      </button>
    </div>

    <div class="ll-records-line"></div>
    ${open ? recordDetail(item) : ""}`;
}

function recordDetail(item) {
  const id = String(item?.doc_id ?? "");
  const status = String(item?.status ?? "");
  const time = String(item?.created_at ?? "")
    .slice(0, 16)
    .replace("T", " at ");

  const info = [
    field("Document id", id),
    field("Ingested", time),
    field("Status", (statusNames[status] || ["", status])[1]),
    field("Processing cost", cost(item?.cost_usd), null, true),
  ].join("");

  let reason = "";

  if (item?.blocked_reason) {
    const label =
      status === "rejected"
        ? "Rejection note"
        : "Blocked by the moderation gate";

    reason = banner("bad", `<b>${label}.</b> ${esc(item.blocked_reason)}`);
  }

  const body = item?.extraction
    ? `<div class="ll-rule">Extracted record</div>${grid(item.extraction)}`
    : banner("pending", "No extracted record is stored for this document.");

  return `
    <div class="detail">
      <div class="detail-grid">
        <div>
          <img
            class="ll-doc-img"
            src="${esc(join(`/image/${encodeURIComponent(id)}`))}"
            alt="Processed document ${esc(id)}"
          >
          <p class="caption">
            The document id and UTC time are shown in the lower right.
          </p>
        </div>

        <div>
          <div class="ll-field-grid ll-field-grid-single">${info}</div>
          <div class="ll-row-text">${esc(item?.filename ?? "")}</div>
        </div>
      </div>

      ${reason}
      ${body}
    </div>`;
}

function timeLeft(seconds) {
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const left = seconds % 60;
  return left ? `${minutes}m ${left}s` : `${minutes}m`;
}

document.addEventListener("click", (e) => {
  const pageBtn = e.target.closest("[data-page]");

  if (pageBtn) {
    e.preventDefault();
    go(pageBtn.dataset.page);
    return;
  }

  const goBtn = e.target.closest("[data-go]");

  if (goBtn) {
    e.preventDefault();
    go(goBtn.dataset.go);
  }
});

themeBtn.addEventListener("click", () => {
  setTheme(app.theme === "dark" ? "light" : "dark");
});

window.addEventListener("beforeunload", () => {
  app.urls.forEach((url) => URL.revokeObjectURL(url));
});

if (!pages.includes(app.page)) app.page = "home";

if (!app.theme) {
  app.theme = window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

setTheme(app.theme, false);
markPage();
go(app.page, false);
