(() => {
  "use strict";

  const $ = (q, p = document) => p.querySelector(q);
  const $$ = (q, p = document) => [...p.querySelectorAll(q)];

  const box = $("#main");
  const note = $("#toast");
  const modeBtn = $("#theme");
  const tag = $("meta[name='theme-color']");
  const rawBase = $("meta[name='api-base']")?.content || "http://localhost:8000";
  const base = rawBase.replace(/\/$/, "");

  const pages = new Set(["home", "upload", "review", "records"]);
  const cash = new Set(["subtotal", "tax", "discount", "additional_charges", "total"]);
  const keys = [
    "vendor", "invoice_number", "date", "currency",
    "subtotal", "tax", "discount", "additional_charges", "total",
  ];
  const hues = [
    "var(--red)", "var(--orange)", "var(--amber)", "var(--green)",
    "var(--teal)", "var(--blue)", "var(--violet)",
  ];
  const MAX_BATCH = 25;
  const GAP_MS = 900;
  const states = {
    auto_approved: ["ok", "auto approved"],
    approved: ["ok", "approved"],
    pending_review: ["pending", "pending review"],
    blocked: ["bad", "blocked"],
    rejected: ["bad", "rejected"],
    error: ["bad", "failed"],
  };

  const mem = {
    page: read("ll-page", "home"),
    theme: read("ll-theme", ""),
    open: read("ll-open", ""),
    files: [],
    urls: [],
    turn: 0,
    timer: 0,
  };

  const pool = new Map();

  function read(k, fallback = "") {
    try {
      return sessionStorage.getItem(k) ?? localStorage.getItem(k) ?? fallback;
    } catch {
      return fallback;
    }
  }

  function save(k, v, keep = false) {
    try {
      (keep ? localStorage : sessionStorage).setItem(k, v);
    } catch {
      // Storage is optional; the page still works without it.
    }
  }

  function esc(v) {
    return String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function title(v) {
    return String(v)
      .replaceAll("_", " ")
      .replace(/\b\w/g, (x) => x.toUpperCase());
  }

  function num(v, d = 2) {
    const x = Number(v);
    if (!Number.isFinite(x)) return "-";
    return x.toLocaleString(undefined, {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  }

  function cost(v, d = 5) {
    const x = Number(v);
    return Number.isFinite(x) ? `$${x.toFixed(d)}` : "$0.00000";
  }

  function wait(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function csvText(rows) {
    const head = [
      "filename", "doc_id", "status", "vendor",
      "total", "currency", "held_fields", "cost_usd",
    ];

    const body = rows.map((r) => [
      r.name, r.doc_id, r.status, r.vendor,
      r.totalRaw, r.currency, r.flagged, r.costRaw,
    ]);

    return [head, ...body]
      .map((cols) =>
        cols
          .map((cell) => {
            const s = String(cell ?? "");
            return /[",\n]/.test(s)
              ? `"${s.replaceAll('"', '""')}"`
              : s;
          })
          .join(","),
      )
      .join("\n");
  }

  function download(text, name) {
    const blob = new Blob([text], {
      type: "text/csv;charset=utf-8",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = name;

    document.body.appendChild(a);
    a.click();
    a.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function batchRow(r, i) {
    const can = Boolean(r.extraction) || Boolean(r.detail);

    const inner = r.extraction
      ? `<div class="batch-detail-grid">
           <div>
             ${
               r.img
                 ? `<img
                      class="ll-doc-img"
                      src="${esc(join(r.img))}"
                      alt="Processed document ${esc(r.doc_id)}"
                    >
                    <p class="caption">
                      The document id and UTC time are shown in the lower right.
                    </p>`
                 : ""
             }
           </div>
           <div>${grid(r.extraction)}${flags(r.held)}</div>
         </div>`
      : banner("bad", esc(r.detail || "No details available."));

    return `
      <tr>
        <td>
          ${esc(r.name)}
          ${
            r.doc_id
              ? `<br><span class="batch-why">${esc(r.doc_id)}</span>`
              : ""
          }
        </td>
        <td>${chip(r.status)}</td>
        <td>${esc(r.vendor || "-")}</td>
        <td class="num money">${esc(r.total)}</td>
        <td class="num">${r.flagged || "-"}</td>
        <td class="num">${cost(r.costRaw)}</td>
        <td class="num">
          ${
            can
              ? `<button
                   class="batch-more"
                   type="button"
                   data-more="${i}"
                   aria-expanded="false"
                   aria-label="Show details for ${esc(r.name)}"
                 >&#9656;</button>`
              : ""
          }
        </td>
      </tr>

      <tr class="batch-detail" data-row="${i}" hidden>
        <td colspan="7">
          <div class="batch-detail-in">${inner}</div>
        </td>
      </tr>`;
  }

  function join(path) {
    if (/^https?:\/\//i.test(String(path))) return String(path);
    return `${base}${String(path).startsWith("/") ? "" : "/"}${path}`;
  }

  async function get(path, fresh = false) {
    const now = Date.now();
    const old = pool.get(path);

    if (!fresh && old && now - old.at < 5000) {
      return old.data;
    }

    const r = await fetch(join(path), {
      headers: {
        Accept: "application/json",
      },
    });

    if (!r.ok) {
      throw new Error(await msg(r));
    }

    const data = await r.json();
    pool.set(path, { at: now, data });

    return data;
  }

  async function send(path, body) {
    const r = await fetch(join(path), {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!r.ok) {
      throw new Error(await msg(r));
    }

    try {
      return await r.json();
    } catch {
      return {};
    }
  }

  async function msg(r) {
    try {
      const data = await r.clone().json();

      if (typeof data?.detail === "string") {
        return data.detail;
      }

      if (data?.detail?.message) {
        return data.detail.message;
      }

      if (data?.message) {
        return data.message;
      }

      return JSON.stringify(data);
    } catch {
      return (await r.text()) || `Request failed (${r.status})`;
    }
  }

  function clear() {
    pool.clear();
  }

  function toast(text) {
    clearTimeout(mem.timer);

    note.textContent = text;
    note.classList.add("show");

    mem.timer = window.setTimeout(() => {
      note.classList.remove("show");
    }, 2600);
  }

  function setMode(value, store = true) {
    const dark = value === "dark";

    mem.theme = dark ? "dark" : "light";
    document.documentElement.dataset.theme = mem.theme;

    const glyph = $("span", modeBtn);
    if (glyph) {
      glyph.innerHTML = dark ? "&#9789;" : "&#9788;";
    }

    modeBtn.title = dark ? "Switch to light mode" : "Switch to dark mode";
    modeBtn.setAttribute("aria-label", modeBtn.title);

    tag?.setAttribute("content", dark ? "#0f1820" : "#f7f3ea");

    if (store) {
      save("ll-theme", mem.theme, true);
    }
  }

  function mark() {
    $$("[data-page]").forEach((b) => {
      const on =
        b.dataset.page === mem.page &&
        b.classList.contains("nav-btn");

      b.classList.toggle("active", on);

      if (b.classList.contains("nav-btn")) {
        b.setAttribute("aria-current", on ? "page" : "false");
      }
    });
  }

  function go(page, focus = true) {
    const next = pages.has(page) ? page : "home";

    mem.page = next;
    save("ll-page", next);

    mem.turn += 1;

    mark();
    draw(next);

    if (focus) {
      window.scrollTo({
        top: 0,
        behavior: "auto",
      });

      requestAnimationFrame(() => {
        box.focus({ preventScroll: true });
      });
    }
  }

  function head(name, sub) {
    return `
      <div class="ll-page-head">
        <div class="ll-page-title rise">${esc(name)}</div>
        <div class="ll-page-sub rise-1">${esc(sub)}</div>
      </div>`;
  }

  function pill(v) {
    const x = Number(v);
    const n = Number.isFinite(x) ? x : 0;
    const c = n >= 0.9 ? "hi" : n >= 0.75 ? "mid" : "lo";

    return `<span class="ll-pill ${c}">${n.toFixed(2)}</span>`;
  }

  function chip(v) {
    const [kind, label] =
      states[v] || ["pending", String(v || "pending")];

    return `<span class="ll-status ${kind}">${esc(label)}</span>`;
  }

  function field(
    label,
    value,
    conf = null,
    money = false,
    hue = "",
  ) {
    const shown =
      value === "" || value == null
        ? "-"
        : esc(value);

    const m =
      money && shown !== "-"
        ? " money"
        : "";

    const p =
      conf == null
        ? ""
        : pill(conf);

    const style =
      hue
        ? ` style="--kc:${esc(hue)}"`
        : "";

    return `
      <div class="ll-field"${style}>
        <div class="ll-field-label">
          <span>${esc(label)}</span>
          ${p}
        </div>
        <div class="ll-field-value${m}" title="${shown}">
          ${shown}
        </div>
      </div>`;
  }

  function grid(data = {}) {
    const cards = keys
      .map((k, i) => {
        const node =
          data[k] || {
            value: null,
            confidence: 0,
          };

        return field(
          title(k),
          node?.value,
          node?.confidence,
          cash.has(k),
          hues[i % hues.length],
        );
      })
      .join("");

    const items =
      Array.isArray(data.line_items)
        ? data.line_items
        : [];

    let rows = "";

    if (items.length) {
      rows = items
        .map(
          (it) => `
            <tr>
              <td>${esc(it?.description ?? "")}</td>
              <td class="num">${num(it?.quantity, 0)}</td>
              <td class="num">${num(it?.unit_price)}</td>
              <td class="num money">${num(it?.amount)}</td>
              <td class="num">${pill(it?.confidence)}</td>
            </tr>`,
        )
        .join("");
    }

    return `
      <div class="ll-field-grid">
        ${cards}
      </div>

      ${
        items.length
          ? `
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

                <tbody>
                  ${rows}
                </tbody>
              </table>
            </div>`
          : ""
      }`;
  }

  function flags(list = []) {
    if (!Array.isArray(list) || !list.length) {
      return "";
    }

    const rows = list
      .map(
        (f) => `
          <tr>
            <td>${esc(f?.field_path ?? "")}</td>
            <td class="num">${esc(f?.value ?? "")}</td>
            <td class="num">${pill(f?.confidence)}</td>
            <td>${esc(f.reason)}</td>
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

          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>`;
  }

  function banner(kind, html) {
    return `<div class="ll-banner ${kind}">${html}</div>`;
  }

  function strip(list) {
    return `
      <div class="ll-summary-strip">
        ${list
          .map(
            ([label, value, hue]) => `
              <div
                class="ll-summary-item"
                style="--metric:${esc(hue)}"
              >
                <span class="ll-summary-value">
                  ${esc(value)}
                </span>

                <span class="ll-summary-label">
                  ${esc(label)}
                </span>
              </div>`,
          )
          .join("")}
      </div>`;
  }

  function draw(page) {
    if (page === "home") {
      home();
    }

    if (page === "upload") {
      upload();
    }

    if (page === "review") {
      review();
    }

    if (page === "records") {
      records();
    }
  }

  async function home() {
    const turn = mem.turn;

    box.innerHTML = `
      <section class="home-hero">
        <div class="home-grid">
          <div>
            <div class="ll-home-copy rise">
              <h1>
                Receipts in.<br>
                <span>Records out.</span>
              </h1>

              <h2>
                Upload a receipt or invoice, check the details,
                and save it to the records.
              </h2>
            </div>

            <button
              class="btn primary hero-btn"
              type="button"
              data-go="upload"
            >
              Extract document
            </button>
          </div>

          <div>
            <div class="ll-receipt-wrap" aria-hidden="true">
              <div class="ll-receipt-pin"></div>

              <div class="ll-home-receipt">
                <div class="ll-receipt-store">
                  Corner Shop
                </div>

                <div class="ll-receipt-meta">
                  12 July | Receipt 1842
                </div>

                <div class="ll-receipt-line">
                  <span>Bread and milk</span>
                  <span>8.40</span>
                </div>

                <div class="ll-receipt-line">
                  <span>Kitchen items</span>
                  <span>11.75</span>
                </div>

                <div class="ll-receipt-line">
                  <span>Tax</span>
                  <span>1.61</span>
                </div>

                <div class="ll-receipt-total">
                  <span>Total</span>
                  <span>21.76</span>
                </div>

                <div class="ll-receipt-note">
                  checked
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div class="ll-home-stats rise-1">
        <div
          class="ll-home-stat"
          style="--stat-color:var(--blue)"
        >
          <span class="value" data-x="all">-</span>
          <span class="label">Uploaded</span>
        </div>

        <div
          class="ll-home-stat"
          style="--stat-color:var(--green)"
        >
          <span class="value" data-x="ok">-</span>
          <span class="label">Approved</span>
        </div>

        <div
          class="ll-home-stat"
          style="--stat-color:var(--amber)"
        >
          <span class="value" data-x="wait">-</span>
          <span class="label">Needs review</span>
        </div>
      </div>`;

    try {
      const docs = await get("/documents");

      if (turn !== mem.turn || mem.page !== "home") {
        return;
      }

      $("[data-x='all']", box).textContent =
        docs.length;

      $("[data-x='ok']", box).textContent =
        docs.filter((d) =>
          ["auto_approved", "approved"].includes(d?.status),
        ).length;

      $("[data-x='wait']", box).textContent =
        docs.filter(
          (d) => d?.status === "pending_review",
        ).length;
    } catch {
      // The home view keeps dashes if the API is unavailable.
    }
  }

function upload() {
    const files = mem.files;
    const has = files.length > 0;

    mem.urls.forEach((u) => URL.revokeObjectURL(u));
    mem.urls = [];

    let preview = `
      <div class="ll-empty-preview">
        <div class="ll-empty-icon"></div>
        <b>No files selected</b>
        <p>Your receipts will appear here.</p>
      </div>`;

    if (has) {
      const kb = files.reduce((n, f) => n + f.size, 0) / 1024;

      const thumbs = files
        .map((f, i) => {
          const u = URL.createObjectURL(f);
          mem.urls.push(u);

          return `
            <figure class="batch-thumb">
              <img src="${esc(u)}" alt="${esc(f.name)}">

              <button
                class="batch-drop"
                type="button"
                data-drop="${i}"
                aria-label="Remove ${esc(f.name)}"
              >x</button>

              <figcaption>${esc(f.name)}</figcaption>
            </figure>`;
        })
        .join("");

      preview = `
        <div class="preview-card">
          <div class="batch-strip">${thumbs}</div>

          <div class="ll-file-meta">
            <span>${files.length} file${
              files.length === 1 ? "" : "s"
            } ready</span>
            <span>${Math.round(kb).toLocaleString()} KB total</span>
          </div>
        </div>`;
    }

    box.innerHTML = `
      ${head(
        "Extract documents",
        "Choose one or more JPG or PNG files. They are read one after another.",
      )}

      <section class="upload-workspace">
        <div class="upload-grid">
          <div>
            <div class="ll-upload-copy">
              <h3>Choose files</h3>

              <p>
                Add a single receipt or a whole batch.
              </p>

              <div class="ll-upload-help">
                <span>JPG or PNG</span>
                <span>One document per image</span>
                <span>Up to ${MAX_BATCH} per batch</span>
              </div>
            </div>

            <label class="dropzone" id="drop">
              <input
                class="file-input"
                id="file"
                type="file"
                accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                multiple hidden
              >

              <span class="dropzone-inner">
                <b>Drop receipts or invoices</b>
                <small>JPG or PNG, one or many</small>
                <span class="choose-btn">Browse files</span>
              </span>
            </label>

            <div class="upload-actions">
              <button
                class="btn primary full"
                id="run"
                type="button"
                ${has ? "" : "disabled"}
              >
                ${
                  has
                    ? `Extract ${files.length} document${
                        files.length === 1 ? "" : "s"
                      }`
                    : "Extract documents"
                }
              </button>

              <p class="upload-note">
                ${
                  has
                    ? `Files are read one at a time. About ${fmtLeft(
                        Math.round((files.length * (12000 + GAP_MS)) / 1000),
                      )} for ${files.length} file${
                        files.length === 1 ? "" : "s"
                      }.`
                    : "Choose files to start."
                }
              </p>
            </div>
          </div>

          <div id="preview">
            ${preview}
          </div>
        </div>
      </section>

      <div id="result" aria-live="polite"></div>`;

    const input = $("#file", box);
    const drop = $("#drop", box);

    input.addEventListener("change", () => {
      pick(input.files);
      input.value = "";
    });

    drop.addEventListener("dragover", (e) => {
      e.preventDefault();
      drop.classList.add("drag");
    });

    drop.addEventListener("dragleave", () => {
      drop.classList.remove("drag");
    });

    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("drag");
      pick(e.dataTransfer?.files);
    });

    $$("[data-drop]", box).forEach((b) => {
      b.addEventListener("click", () => {
        mem.files.splice(Number(b.dataset.drop), 1);
        upload();
      });
    });

    $("#run", box).addEventListener("click", ingest);
  }

  function pick(list) {
    const incoming = [...(list || [])];

    if (!incoming.length) {
      return;
    }

    const good = incoming.filter(
      (f) =>
        ["image/jpeg", "image/png"].includes(f.type) ||
        /\.(jpe?g|png)$/i.test(f.name),
    );

    if (!good.length) {
      toast("Choose JPG or PNG files.");
      return;
    }

    const room = Math.max(MAX_BATCH - mem.files.length, 0);
    const added = good.slice(0, room);

    mem.files = mem.files.concat(added);

    const skipped = incoming.length - good.length;

    if (skipped) {
      toast(
        `${skipped} file${
          skipped === 1 ? "" : "s"
        } skipped. JPG or PNG only.`,
      );
    } else if (added.length < good.length) {
      toast(`Limit is ${MAX_BATCH} files per batch.`);
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

    const data = new FormData();
    data.append("file", file, file.name);

    let r;

    try {
      r = await fetch(join("/ingest"), {
        method: "POST",
        headers: { Accept: "application/json" },
        body: data,
      });
    } catch (e) {
      out.detail = `API unreachable: ${e.message}`;
      return out;
    }

    if (r.status === 429 && attempt < 3) {
      await wait(3000 * (attempt + 1));
      return ingestOne(file, attempt + 1);
    }

    if (r.status === 422) {
      out.status = "blocked";

      try {
        const d = await r.json();
        out.doc_id = String(d?.detail?.doc_id ?? "");
        out.detail =
          d?.detail?.blocked_reason ||
          "Blocked by the moderation gate.";
      } catch {
        out.detail = "Blocked by the moderation gate.";
      }

      return out;
    }

    if (!r.ok) {
      out.detail = await msg(r);
      return out;
    }

    let d;

    try {
      d = await r.json();
    } catch {
      out.detail = "The API returned an unreadable response.";
      return out;
    }

    const ex = d.extraction || {};
    const total = Number(ex?.total?.value);

    out.doc_id = String(d.doc_id ?? "");
    out.status = String(d.status ?? "");
    out.vendor = String(ex?.vendor?.value ?? "");
    out.currency = String(ex?.currency?.value ?? "");
    out.totalRaw = Number.isFinite(total) ? total : "";
    out.total = Number.isFinite(total) ? num(total) : "-";
    out.flagged = Array.isArray(d.flagged_fields)
      ? d.flagged_fields.length
      : 0;
    out.costRaw = Number(d.cost_usd) || 0;
    out.extraction = ex;
    out.held = Array.isArray(d.flagged_fields) ? d.flagged_fields : [];
    out.img = String(d.watermarked_image_url || "");


    return out;
  }

  async function ingest() {
    const files = mem.files.slice();

    if (!files.length) {
      return;
    }

    const btn = $("#run", box);
    const out = $("#result", box);
    const turn = mem.turn;

    btn.disabled = true;

    out.innerHTML = `
      <div class="ll-rule">Extraction results</div>

      <div class="batch-progress">
        <div class="batch-progress-bar">
          <span id="pbar"></span>
        </div>
        <p class="batch-progress-text" id="ptext">
          Starting...
        </p>
      </div>

      <div class="ll-table-wrap">
        <table class="ll-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Status</th>
              <th>Vendor</th>
              <th>Total</th>
              <th>Held</th>
              <th>Cost</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="brows"></tbody>
        </table>
      </div>

      <div class="batch-actions" id="bactions"></div>`;

    const bar = $("#pbar", box);
    const text = $("#ptext", box);
    const rows = $("#brows", box);
    const done = [];
    const started = Date.now();

    rows.addEventListener("click", (e) => {
      const b = e.target.closest("[data-more]");
      if (!b) return;

      const panel = $(
        `.batch-detail[data-row="${b.dataset.more}"]`,
        rows,
      );
      if (!panel) return;

      const show = panel.hasAttribute("hidden");

      panel.toggleAttribute("hidden", !show);
      b.setAttribute("aria-expanded", String(show));
      b.classList.toggle("open", show);
    });

    for (let i = 0; i < files.length; i += 1) {
      if (turn !== mem.turn || mem.page !== "upload") {
        return;
      }

      const avg = i > 0 ? (Date.now() - started) / i : 0;
      const left = avg ? Math.round((avg * (files.length - i)) / 1000) : 0;

      text.textContent =
        `Reading ${i + 1} of ${files.length}: ${files[i].name}` +
        (left ? ` · about ${fmtLeft(left)} remaining` : "");

      bar.style.width = `${Math.round((i / files.length) * 100)}%`;

      const res = await ingestOne(files[i]);

      if (turn !== mem.turn || mem.page !== "upload") {
        return;
      }

      done.push(res);
      rows.insertAdjacentHTML("beforeend", batchRow(res, i));

      bar.style.width = `${Math.round(
        ((i + 1) / files.length) * 100,
      )}%`;

      if (i < files.length - 1) {
        await wait(GAP_MS);
      }
    }

    clear();

    const okCount = done.filter(
      (r) => r.status === "auto_approved",
    ).length;

    const waitCount = done.filter(
      (r) => r.status === "pending_review",
    ).length;

    const badCount = done.length - okCount - waitCount;

    const spend = done.reduce(
      (n, r) => n + (Number(r.costRaw) || 0),
      0,
    );

    text.textContent =
      `Done. ${okCount} approved, ${waitCount} sent to review, ` +
      `${badCount} failed or blocked. Spend ${cost(spend)}.`;

    $("#bactions", box).innerHTML = `
      <button
        class="btn secondary small"
        type="button"
        id="csv"
      >Download CSV summary</button>

      ${
        waitCount
          ? `<button
               class="btn primary small"
               type="button"
               data-go="review"
             >Open review queue</button>`
          : ""
      }`;

    $("#csv", box).addEventListener("click", () => {
      download(
        csvText(done),
        `recordslens-batch-${Date.now()}.csv`,
      );
    });

    btn.disabled = false;
  }

  async function review(fresh = false) {
    const turn = mem.turn;

    box.innerHTML = `
      <div class="page-top">
        ${head(
          "Review queue",
          "Check the document, fix any values, then approve or reject it.",
        )}

        <button
          class="btn secondary small"
          type="button"
          id="reload"
          style="font-size:1rem;"
        >
          &#x27F3;
        </button>
      </div>

      <div id="review-box">
        <div class="loader">
          Loading the review queue...
        </div>
      </div>`;

    $("#reload", box).addEventListener(
      "click",
      () => review(true),
    );

    let list;

    try {
      list = await get("/review", fresh);
    } catch (e) {
      if (
        turn === mem.turn &&
        mem.page === "review"
      ) {
        $("#review-box", box).innerHTML =
          banner(
            "bad",
            `<b>API unreachable.</b> ${esc(e.message)}`,
          );
      }

      return;
    }

    if (
      turn !== mem.turn ||
      mem.page !== "review"
    ) {
      return;
    }

    const area = $("#review-box", box);

    if (!Array.isArray(list) || !list.length) {
      area.innerHTML =
        banner(
          "ok",
          "No documents need review.",
        );

      return;
    }

    area.innerHTML = `
      <div class="review-count">
        ${chip("pending_review").replace(
          "pending review",
          `${list.length} document${
            list.length === 1 ? "" : "s"
          } waiting`,
        )}
      </div>

      <div class="review-list">
        ${list
          .map(
            (item, i) =>
              reviewItem(
                item,
                list.length === 1 && i === 0,
              ),
          )
          .join("")}
      </div>`;

    $$('[data-do="reject"]', area).forEach(
      (b) => {
        b.addEventListener(
          "click",
          () => rejectOne(b, list),
        );
      },
    );

    $$('[data-do="approve"]', area).forEach(
      (b) => {
        b.addEventListener(
          "click",
          () => approveOne(b, list),
        );
      },
    );
  }

  function reviewItem(item, open) {
    const id = String(item?.doc_id ?? "");

    const list =
      Array.isArray(item?.flagged_fields)
        ? item.flagged_fields
        : [];

    const rows = list
      .map((f, i) => {
        const path =
          String(f?.field_path ?? "");

        const value =
          String(f?.value ?? "");

        return `
          <div class="correction-row">
            <div>
              <div class="ll-correction-label">
                ${esc(path)}
              </div>

              <div class="ll-correction-value">
                ${esc(value)}
              </div>

              <div class="ll-correction-help">
                Confidence ${pill(f?.confidence)}
              </div>
            </div>

            <div>
              <label
                class="ll-correction-label"
                for="fix-${esc(id)}-${i}"
              >
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
      <details
        class="review-item"
        data-id="${esc(id)}"
        ${open ? "open" : ""}
      >
        <summary>
          ${esc(item?.filename ?? "")}
          |
          ${esc(id)}
          |
          ${list.length} field${
            list.length === 1 ? "" : "s"
          } held
        </summary>

        <div class="review-body">
          <div class="review-grid">
            <div>
              <img
                class="ll-doc-img"
                src="${esc(
                  join(
                    item?.watermarked_image_url || "",
                  ),
                )}"
                alt="Watermarked document ${esc(id)}"
              >
            </div>

            <div>
              ${grid(item?.extraction || {})}
            </div>
          </div>

          <div class="ll-rule">
            Correct the held fields
          </div>

          ${rows}

          <div class="form-row">
            <label for="reason-${esc(id)}">
              Reason, if rejecting
            </label>

            <input
              class="text-input"
              id="reason-${esc(id)}"
              data-reason
              value="Not a valid receipt/invoice"
            >
          </div>

          <div class="review-actions">
            <button
              class="btn primary"
              type="button"
              data-do="approve"
            >
              Approve
            </button>

            <button
              class="btn secondary"
              type="button"
              data-do="reject"
            >
              Reject
            </button>

            <span></span>
          </div>
        </div>
      </details>`;
  }

  function itemFrom(btn, list) {
    const node =
      btn.closest(".review-item");

    const id =
      node?.dataset.id || "";

    return [
      node,
      list.find(
        (x) =>
          String(x?.doc_id ?? "") === id,
      ),
    ];
  }

  function lock(node, on) {
    $$("button[data-do]", node).forEach(
      (b) => {
        b.disabled = on;
      },
    );
  }

  async function rejectOne(btn, list) {
    const [node, item] =
      itemFrom(btn, list);

    if (!node || !item) {
      return;
    }

    lock(node, true);

    const reason =
      $("[data-reason]", node)?.value ||
      "Not a valid receipt/invoice";

    try {
      await send("/reject", {
        doc_id: item.doc_id,
        reason,
      });

      clear();
      toast("Rejected.");
      review(true);
    } catch (e) {
      toast(`Reject failed: ${e.message}`);
      lock(node, false);
    }
  }

  async function approveOne(btn, list) {
    const [node, item] =
      itemFrom(btn, list);

    if (!node || !item) {
      return;
    }

    lock(node, true);

    const corrections =
      $$("input[data-f]", node)
        .filter(
          (x) =>
            x.value !== x.dataset.old,
        )
        .map((x) => ({
          field_path: x.dataset.f,
          corrected_value: x.value,
        }));

    try {
      const data = await send(
        "/approve",
        {
          doc_id: item.doc_id,
          corrections,
        },
      );

      const n =
        Number(data?.applied_corrections) || 0;

      clear();

      toast(
        `Approved, ${n} correction${
          n === 1 ? "" : "s"
        }.`,
      );

      review(true);
    } catch (e) {
      toast(`Approve failed: ${e.message}`);
      lock(node, false);
    }
  }

  async function records(fresh = false) {
    const turn = mem.turn;

    box.innerHTML = `
      ${head(
        "Records",
        "See every processed document. Open a row to view the image and details.",
      )}

      <div id="records-box">
        <div class="loader">
          Loading documents...
        </div>
      </div>`;

    let docs;

    try {
      docs = await get(
        "/documents",
        fresh,
      );
    } catch (e) {
      if (
        turn === mem.turn &&
        mem.page === "records"
      ) {
        $("#records-box", box).innerHTML =
          banner(
            "bad",
            `<b>API unreachable.</b> ${esc(e.message)}`,
          );
      }

      return;
    }

    if (
      turn !== mem.turn ||
      mem.page !== "records"
    ) {
      return;
    }

    showRecords(
      Array.isArray(docs) ? docs : [],
    );
  }

  function showRecords(docs) {
    const area = $("#records-box", box);

    if (!docs.length) {
      area.innerHTML =
        banner(
          "pending",
          "No documents have been uploaded yet.",
        );

      return;
    }

    const auto =
      docs.filter(
        (d) =>
          d?.status === "auto_approved",
      ).length;

    const ok =
      docs.filter(
        (d) =>
          d?.status === "approved",
      ).length;

    const wait =
      docs.filter(
        (d) =>
          d?.status === "pending_review",
      ).length;

    const bad =
      docs.filter((d) =>
        ["rejected", "blocked"].includes(
          d?.status,
        ),
      ).length;

    const total =
      docs.reduce(
        (n, d) =>
          n + (Number(d?.cost_usd) || 0),
        0,
      );

    area.innerHTML = `
      ${strip([
        [
          "Auto approved",
          auto,
          "var(--teal)",
        ],
        [
          "Approved",
          ok,
          "var(--green)",
        ],
        [
          "Needs review",
          wait,
          "var(--amber)",
        ],
        [
          "Rejected or blocked",
          bad,
          "var(--red)",
        ],
        [
          "Processing cost",
          `$${total.toFixed(4)}`,
          "var(--violet)",
        ],
      ])}

      <div class="ll-rule">
        All documents
      </div>

      <div class="records-wrap">
        <div class="records">
          <div class="records-head">
            <span class="ll-col-head">
              File
            </span>

            <span class="ll-col-head">
              Status
            </span>

            <span class="ll-col-head">
              Vendor
            </span>

            <span class="ll-col-head">
              Total
            </span>

            <span class="ll-col-head">
              Ingested
            </span>

            <span class="ll-col-head"></span>
          </div>

          ${docs
            .map((d) => recordsRow(d))
            .join("")}
        </div>
      </div>`;

    $$('[data-do="open"]', area).forEach(
      (b) => {
        b.addEventListener("click", () => {
          const id = b.dataset.id || "";

          mem.open =
            mem.open === id
              ? ""
              : id;

          save("ll-open", mem.open);
          showRecords(docs);
        });
      },
    );
  }

  function recordsRow(d) {
    const id =
      String(d?.doc_id ?? "");

    const open =
      mem.open === id;

    const total =
      Number(d?.total);

    const shown =
      Number.isFinite(total)
        ? num(total)
        : "-";

    const time =
      String(d?.created_at ?? "")
        .slice(0, 16)
        .replace("T", " at ");

    return `
      <div class="records-row">
        <div class="ll-row-text">
          ${esc(d?.filename ?? "")}
          <br>
          <span class="mono">
            ${esc(id)}
          </span>
        </div>

        <div>
          ${chip(d?.status)}
        </div>

        <div class="ll-row-text">
          ${esc(d?.vendor || "-")}
        </div>

        <div class="ll-money-cell">
          ${shown}
        </div>

        <div class="ll-row-text">
          <span class="mono">
            ${esc(time)}
          </span>
        </div>

        <button
          class="btn ${
            open
              ? "primary"
              : "secondary"
          } small"
          type="button"
          data-do="open"
          data-id="${esc(id)}"
        >
          ${open ? "Hide" : "Details"}
        </button>
      </div>

      <div class="ll-records-line"></div>

      ${open ? detail(d) : ""}`;
  }

  function detail(d) {
    const id = String(d?.doc_id ?? "");
    const total = Number(d?.total);
    const status = String(d?.status ?? "");

    const meta = [
      field("Document id", id, null, false, "var(--blue)"),
      field(
        "Ingested",
        String(d?.created_at ?? "").slice(0, 16).replace("T", " at "),
        null,
        false,
        "var(--teal)",
      ),
      field("Status", (states[status] || ["", status])[1], null, false, "var(--amber)"),
      field("Processing cost", cost(d?.cost_usd), null, true, "var(--violet)"),
    ].join("");

    let why = "";

    if (d?.blocked_reason) {
      why = banner(
        "bad",
        `<b>${
          status === "rejected"
            ? "Rejection note"
            : "Blocked by the moderation gate"
        }.</b> ${esc(d.blocked_reason)}`,
      );
    }

    const body = d?.extraction
      ? `
        <div class="ll-rule">Extracted record</div>
        ${grid(d.extraction)}`
      : banner(
          "pending",
          "No extracted record is stored for this document.",
        );

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
            <div class="ll-field-grid ll-field-grid-single">
              ${meta}
            </div>

            <div class="ll-row-text">
              ${esc(d?.filename ?? "")}
            </div>
          </div>
        </div>

        ${why}
        ${body}
      </div>`;
  }

  function fmtLeft(sec) {
    if (sec < 60) {
      return `${sec}s`;
    }

    const m = Math.floor(sec / 60);
    const s = sec % 60;

    return s ? `${m}m ${s}s` : `${m}m`;
  }


  document.addEventListener("click", (e) => {
    const nav =
      e.target.closest("[data-page]");

    if (nav) {
      e.preventDefault();
      go(nav.dataset.page);
      return;
    }

    const jump =
      e.target.closest("[data-go]");

    if (jump) {
      e.preventDefault();
      go(jump.dataset.go);
    }
  });

  modeBtn.addEventListener("click", () => {
    setMode(
      mem.theme === "dark"
        ? "light"
        : "dark",
    );
  });

  window.addEventListener(
    "beforeunload",
    () => {
      mem.urls.forEach((u) => URL.revokeObjectURL(u));
    },
  );

  if (!pages.has(mem.page)) {
    mem.page = "home";
  }

  if (!mem.theme) {
    mem.theme =
      window.matchMedia?.(
        "(prefers-color-scheme: dark)",
      ).matches
        ? "dark"
        : "light";
  }

  setMode(mem.theme, false);
  mark();
  go(mem.page, false);
})();