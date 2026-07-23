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

  const pages = new Set(["home", "upload", "review", "ledger"]);
  const cash = new Set(["subtotal", "tax", "discount", "additional_charges", "total"]);
  const keys = [
    "vendor", "invoice_number", "date", "currency",
    "subtotal", "tax", "discount", "additional_charges", "total",
  ];
  const hues = [
    "var(--red)", "var(--orange)", "var(--amber)", "var(--green)",
    "var(--teal)", "var(--blue)", "var(--violet)",
  ];
  const states = {
    auto_approved: ["ok", "auto approved"],
    approved: ["ok", "approved"],
    pending_review: ["pending", "pending review"],
    blocked: ["bad", "blocked"],
    rejected: ["bad", "rejected"],
  };

  const mem = {
    page: read("ll-page", "home"),
    theme: read("ll-theme", ""),
    open: read("ll-open", ""),
    file: null,
    url: "",
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

    modeBtn.textContent = dark ? "Light" : "Dark";
    modeBtn.title = dark ? "Use light mode" : "Use dark mode";
    modeBtn.setAttribute("aria-label", modeBtn.title);

    tag?.setAttribute(
      "content",
      dark ? "#0f1820" : "#f7f3ea",
    );

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

    if (page === "ledger") {
      ledger();
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
                and save it to the ledger.
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
    const has = mem.file instanceof File;

    let preview = `
      <div class="ll-empty-preview">
        <div class="ll-empty-icon"></div>
        <b>No file selected</b>
        <p>Your receipt will appear here.</p>
      </div>`;

    if (has) {
      if (mem.url) {
        URL.revokeObjectURL(mem.url);
      }

      mem.url = URL.createObjectURL(mem.file);

      preview = `
        <div class="preview-card">
          <img
            src="${esc(mem.url)}"
            alt="Selected receipt or invoice preview"
          >

          <div class="ll-file-meta">
            <span>${esc(mem.file.name)}</span>
            <span>
              ${Math.round(
                mem.file.size / 1024,
              ).toLocaleString()} KB
            </span>
          </div>
        </div>`;
    }

    box.innerHTML = `
      ${head(
        "Extract document",
        "Choose a JPG or PNG. Review the result after it is read.",
      )}

      <section class="upload-workspace">
        <div class="upload-grid">
          <div>
            <div class="ll-upload-copy">
              <h3>Choose a file</h3>

              <p>
                Use one clear receipt or invoice.
              </p>

              <div class="ll-upload-help">
                <span>JPG or PNG</span>
                <span>One document per image</span>
                <span>Fix fields when needed</span>
              </div>
            </div>

            <label class="dropzone" id="drop">
              <input
                class="file-input"
                id="file"
                type="file"
                accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              >

              <span class="dropzone-inner">
                <b>Drop a receipt or invoice</b>
                <small>JPG or PNG</small>
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
                Extract document
              </button>

              <p class="upload-note">
                ${
                  has
                    ? "Ready to extract."
                    : "Choose a file to start."
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
      pick(input.files?.[0]);
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
      pick(e.dataTransfer?.files?.[0]);
    });

    $("#run", box).addEventListener("click", ingest);
  }

  function pick(file) {
    if (!file) {
      return;
    }

    const ok =
      ["image/jpeg", "image/png"].includes(file.type) ||
      /\.(jpe?g|png)$/i.test(file.name);

    if (!ok) {
      toast("Choose a JPG or PNG file.");
      return;
    }

    mem.file = file;
    upload();
  }

  async function ingest() {
    if (!(mem.file instanceof File)) {
      return;
    }

    const btn = $("#run", box);
    const out = $("#result", box);
    const turn = mem.turn;

    btn.disabled = true;

    out.innerHTML = `
      <div class="ll-rule">
        Extraction result
      </div>

      <div class="loader">
        Reading the document...
      </div>`;

    const data = new FormData();

    data.append(
      "file",
      mem.file,
      mem.file.name,
    );

    let r;

    try {
      r = await fetch(join("/ingest"), {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
        body: data,
      });
    } catch (e) {
      if (
        turn === mem.turn &&
        mem.page === "upload"
      ) {
        out.innerHTML = `
          <div class="ll-rule">
            Extraction result
          </div>

          ${banner(
            "bad",
            `<b>API unreachable.</b> ${esc(e.message)}`,
          )}`;

        btn.disabled = false;
      }

      return;
    }

    if (
      turn !== mem.turn ||
      mem.page !== "upload"
    ) {
      return;
    }

    clear();

    if (r.status === 422) {
      let why = "The document was flagged.";

      try {
        const d = await r.json();

        why =
          d?.detail?.blocked_reason ||
          d?.detail ||
          why;
      } catch {
        // Use the default message.
      }

      out.innerHTML = `
        <div class="ll-rule">
          Extraction result
        </div>

        ${banner(
          "bad",
          `<b>Blocked.</b> ${esc(why)}`,
        )}`;

      btn.disabled = false;
      return;
    }

    if (r.status !== 200) {
      out.innerHTML = `
        <div class="ll-rule">
          Extraction result
        </div>

        ${banner(
          "bad",
          `<b>Error ${r.status}.</b> ${esc(
            await msg(r),
          )}`,
        )}`;

      btn.disabled = false;
      return;
    }

    let d;

    try {
      d = await r.json();
    } catch {
      out.innerHTML = `
        <div class="ll-rule">
          Extraction result
        </div>

        ${banner(
          "bad",
          "The API returned an unreadable response.",
        )}`;

      btn.disabled = false;
      return;
    }

    const list =
      Array.isArray(d.flagged_fields)
        ? d.flagged_fields
        : [];

    const top =
      d.status === "auto_approved"
        ? banner(
            "ok",
            `<b>Approved.</b> All fields passed the checks. ` +
              `Doc <span class="mono">${esc(d.doc_id)}</span> ` +
              `| <span class="mono">${cost(d.cost_usd)}</span>`,
          )
        : banner(
            "pending",
            `<b>${list.length} field${
              list.length === 1 ? "" : "s"
            } need review.</b> ` +
              `The document is in the Review queue. ` +
              `Doc <span class="mono">${esc(d.doc_id)}</span> ` +
              `| <span class="mono">${cost(d.cost_usd)}</span>`,
          );

    out.innerHTML = `
      <div class="ll-rule">
        Extraction result
      </div>

      ${top}
      ${grid(d.extraction || {})}
      ${flags(list)}`;

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
        >
          Refresh
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

  async function ledger(fresh = false) {
    const turn = mem.turn;

    box.innerHTML = `
      ${head(
        "Ledger",
        "See every processed document. Open a row to view the image and details.",
      )}

      <div id="ledger-box">
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
        mem.page === "ledger"
      ) {
        $("#ledger-box", box).innerHTML =
          banner(
            "bad",
            `<b>API unreachable.</b> ${esc(e.message)}`,
          );
      }

      return;
    }

    if (
      turn !== mem.turn ||
      mem.page !== "ledger"
    ) {
      return;
    }

    showLedger(
      Array.isArray(docs) ? docs : [],
    );
  }

  function showLedger(docs) {
    const area = $("#ledger-box", box);

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

      <div class="ledger-wrap">
        <div class="ledger">
          <div class="ledger-head">
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
            .map((d) => ledgerRow(d))
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
          showLedger(docs);
        });
      },
    );
  }

  function ledgerRow(d) {
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
      <div class="ledger-row">
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
          ${open ? "Close" : "Open"}
        </button>
      </div>

      <div class="ll-ledger-line"></div>

      ${open ? detail(d) : ""}`;
  }

  function detail(d) {
    const id =
      String(d?.doc_id ?? "");

    const total =
      Number(d?.total);

    const cards = [
      field(
        "Vendor",
        d?.vendor || "-",
        null,
        false,
        "var(--blue)",
      ),

      field(
        "Total",
        Number.isFinite(total)
          ? num(total)
          : "-",
        null,
        true,
        "var(--green)",
      ),

      field(
        "Currency",
        d?.currency || "-",
        null,
        false,
        "var(--teal)",
      ),

      field(
        "Cost",
        cost(d?.cost_usd),
        null,
        true,
        "var(--violet)",
      ),
    ].join("");

    return `
      <div class="detail">
        <div class="detail-grid">
          <div>
            <img
              class="ll-doc-img"
              src="${esc(
                join(
                  `/image/${encodeURIComponent(id)}`,
                ),
              )}"
              alt="Processed document ${esc(id)}"
            >

            <p class="caption">
              The document id and UTC time are shown
              in the lower right.
            </p>
          </div>

          <div>
            <div
              class="ll-field-grid ll-field-grid-single"
            >
              ${cards}
            </div>

            ${chip(d?.status)}
          </div>
        </div>
      </div>`;
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
      if (mem.url) {
        URL.revokeObjectURL(mem.url);
      }
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