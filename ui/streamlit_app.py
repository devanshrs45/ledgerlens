"""LedgerLens, a document intelligence UI.

Four pages behind a fixed top navigation bar. Colorful, friendly, a little
old-web: a rainbow underline on the nav, an animated notebook-paper hero,
cards that each get their own color. Theme starts on the system preference
and flips with one small round button.
"""

import html as html_lib
import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="LedgerLens · receipts, read and reconciled",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------------------------------------------------------------------- #
# State + theme
# --------------------------------------------------------------------------- #
if "page" not in st.session_state:
    st.session_state.page = "home"
if "open_doc" not in st.session_state:
    st.session_state.open_doc = None


def system_theme() -> str:
    try:
        t = st.context.theme.type  # "light" | "dark" (Streamlit 1.46+)
        return t if t in ("light", "dark") else "light"
    except Exception:
        return "light"


if "theme" not in st.session_state:
    st.session_state.theme = system_theme()

DARK = st.session_state.theme == "dark"

# Seven named hues per mode, tuned for contrast against that mode's surfaces.
LIGHT_VARS = """
    --bg:#fdf9f3; --surface:#ffffff; --surface2:#f6efe6; --line:#e9dfd2;
    --text:#2c2118; --text2:#82705f;
    --red:#d64545; --orange:#e0731d; --amber:#c98f10; --green:#2e9960;
    --teal:#12968b; --blue:#2f7fd4; --violet:#8a55c9;
    --ok:#22794f; --ok-bg:#e2f1e8; --warn:#96660f; --warn-bg:#f9efd9;
    --bad:#c03a35; --bad-bg:#f9e6e3;
    --paperline:#dfe8f2; --margin:#f0b6b3;
    --shadow:rgba(96,64,32,0.08); --navglow:rgba(224,115,29,0.10);
"""
DARK_VARS = """
    --bg:#191420; --surface:#231d2c; --surface2:#2e2738; --line:#3e3549;
    --text:#f1eae2; --text2:#a795a0;
    --red:#ff7a72; --orange:#ffa14e; --amber:#ffcb52; --green:#4fd68f;
    --teal:#2fd4c2; --blue:#63aaff; --violet:#c08cf0;
    --ok:#5fc78f; --ok-bg:#21362b; --warn:#e0b45f; --warn-bg:#362c1a;
    --bad:#f28b80; --bad-bg:#3c2528;
    --paperline:#332c40; --margin:#7c4a55;
    --shadow:rgba(0,0,0,0.45); --navglow:rgba(255,161,78,0.08);
"""

st.markdown(
    f"<style>:root {{{DARK_VARS if DARK else LIGHT_VARS}}}</style>",
    unsafe_allow_html=True,
)

# Main stylesheet, plain string so CSS braces need no escaping.
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;1,9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');

[data-testid="stToolbar"], [data-testid="stHeader"],
[data-testid="stDecoration"], footer, #MainMenu { display:none !important; }

html, body, [class*="css"] { font-family:'Inter',sans-serif; }
.stApp { background:var(--bg); transition:background .3s ease; }
.block-container { padding-top:5.4rem; max-width:1150px; }
h1,h2,h3,h4,p,li,label,.stMarkdown { color:var(--text); }
small,.stCaption,[data-testid="stCaptionContainer"] { color:var(--text2) !important; }

/* ---------- motion ---------- */
@keyframes rise  { from { opacity:0; transform:translateY(12px); }
                   to   { opacity:1; transform:none; } }
@keyframes paper { from { background-position:0 0, 0 0; }
                   to   { background-position:0 240px, 0 0; } }
@keyframes inkline { from { width:0; } to { width:6.5rem; } }
.rise   { animation:rise .5s ease both; }
.rise-1 { animation:rise .5s .08s ease both; }
.rise-2 { animation:rise .5s .16s ease both; }
.rise-3 { animation:rise .5s .24s ease both; }

/* ---------- fixed top navigation ---------- */
.st-key-topnav {
    position:fixed; top:0; left:50%; transform:translateX(-50%);
    width:min(1150px, calc(100% - 1.6rem));
    z-index:9999;
    background:var(--surface);
    border:1px solid var(--line); border-top:none;
    border-radius:0 0 14px 14px;
    padding:0.45rem 0.9rem 0.55rem;
    box-shadow:0 4px 18px var(--shadow), 0 2px 10px var(--navglow);
}
.st-key-topnav::after {
    content:""; position:absolute; left:0; right:0; bottom:0; height:4px;
    border-radius:0 0 14px 14px;
    background:linear-gradient(90deg,
        var(--red), var(--orange), var(--amber), var(--green),
        var(--teal), var(--blue), var(--violet));
}
.ll-wordmark {
    font-family:'Fraunces',serif; font-weight:700; font-size:1.35rem;
    letter-spacing:-0.01em; line-height:1.9;
    background:linear-gradient(100deg,
        var(--red), var(--orange) 35%, var(--violet));
    -webkit-background-clip:text; background-clip:text; color:transparent;
}
.st-key-topnav .stButton > button {
    border:none; background:transparent; padding:0.35rem 0.6rem;
}
.st-key-themebtn .stButton > button {
    width:2.15rem; height:2.15rem; min-height:2.15rem; padding:0;
    border-radius:99px; font-size:0.95rem; line-height:1;
    background:var(--surface2); border:1px solid var(--line);
    color:var(--text);
}
.st-key-themebtn .stButton > button:hover {
    border-color:var(--orange); color:var(--orange);
}

/* ---------- notebook hero ---------- */
.ll-hero {
    position:relative; padding:3.1rem 1.5rem 2.7rem 5.2rem;
    border-radius:16px; overflow:hidden;
    border:1px solid var(--line);
    box-shadow:0 4px 20px var(--shadow);
    margin-bottom:1.5rem;
    background:
      repeating-linear-gradient(to bottom,
        var(--surface) 0, var(--surface) 29px,
        var(--paperline) 29px, var(--paperline) 30px),
      var(--surface);
    animation:paper 24s linear infinite;
}
.ll-hero::before {
    content:""; position:absolute; top:0; bottom:0; left:3.6rem; width:2px;
    background:var(--margin);
}
.ll-hero h1 {
    font-family:'Fraunces',serif; font-weight:700; font-size:2.8rem;
    letter-spacing:-0.02em; margin:0 0 0.55rem; line-height:1.15;
}
.ll-hero h1 .c1 { color:var(--orange); font-style:italic; }
.ll-hero h1 .c2 { color:var(--violet); font-style:italic; }
.ll-hero .ink {
    height:3px; border-radius:3px; margin:0.1rem 0 0.9rem;
    background:linear-gradient(90deg, var(--red), var(--amber));
    animation:inkline .9s .3s ease both;
}
.ll-hero p {
    font-size:1.02rem; color:var(--text2); max-width:560px;
    margin:0; line-height:1.7;
}

/* ---------- headings ---------- */
.ll-rule {
    display:flex; align-items:center; gap:0.7rem;
    font-family:'Fraunces',serif; font-weight:600; font-size:1.12rem;
    color:var(--text); margin:1.6rem 0 0.7rem;
}
.ll-rule::after { content:""; flex:1; height:2px; border-radius:2px;
    background:linear-gradient(90deg, var(--line), transparent); }
.ll-page-title {
    font-family:'Fraunces',serif; font-weight:700; font-size:1.65rem;
    margin:0 0 0.15rem; color:var(--text);
}
.ll-page-title .c1 { color:var(--orange); font-style:italic; }
.ll-page-sub { font-size:0.9rem; color:var(--text2); margin-bottom:1.1rem; }

/* ---------- feature cards, each its own color ---------- */
.ll-feature {
    background:var(--surface); border:1px solid var(--line);
    border-top:4px solid var(--fc, var(--orange));
    border-radius:12px; padding:1rem 1.1rem; height:100%;
    box-shadow:0 2px 8px var(--shadow);
    transition:transform .18s ease, box-shadow .18s ease;
}
.ll-feature:hover { transform:translateY(-4px); box-shadow:0 10px 22px var(--shadow); }
.ll-feature h4 {
    font-family:'Fraunces',serif; font-size:1rem; font-weight:600;
    margin:0 0 0.35rem; color:var(--fc, var(--orange));
}
.ll-feature p { font-size:0.86rem; color:var(--text2); margin:0; line-height:1.6; }

/* ---------- steps, colored chips ---------- */
.ll-step {
    display:flex; gap:0.85rem; align-items:flex-start;
    background:var(--surface); border:1px solid var(--line);
    border-radius:12px; padding:0.75rem 0.95rem; margin-bottom:0.5rem;
    box-shadow:0 1px 4px var(--shadow);
    transition:transform .16s ease, border-color .16s ease;
}
.ll-step:hover { transform:translateX(5px); border-color:var(--sc, var(--teal)); }
.ll-step .n {
    font-family:'JetBrains Mono',monospace; font-size:0.76rem;
    color:#fff; background:var(--sc, var(--teal));
    border-radius:7px; padding:0.16rem 0.5rem; margin-top:0.1rem;
}
.ll-step .t { font-weight:600; font-size:0.9rem; color:var(--text); }
.ll-step .d { font-size:0.83rem; color:var(--text2); line-height:1.55; }

/* ---------- field / stat cards ---------- */
.ll-field {
    background:var(--surface); border:1px solid var(--line);
    border-left:4px solid var(--kc, var(--line));
    border-radius:10px; padding:0.58rem 0.8rem 0.5rem;
    margin-bottom:0.6rem; box-shadow:0 1px 4px var(--shadow);
    transition:transform .15s ease, box-shadow .15s ease;
}
.ll-field:hover { transform:translateY(-2px); box-shadow:0 6px 14px var(--shadow); }
.ll-field-label {
    font-size:0.65rem; font-weight:600; letter-spacing:0.08em;
    text-transform:uppercase; color:var(--text2);
    display:flex; justify-content:space-between; align-items:center;
    gap:0.4rem; margin-bottom:0.18rem;
}
.ll-field-value {
    font-family:'JetBrains Mono',monospace; font-weight:500;
    font-size:1.1rem; color:var(--text);
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.ll-field-value.money { color:var(--kc, var(--green)); }

/* ---------- confidence + status ---------- */
.ll-pill {
    font-family:'JetBrains Mono',monospace; font-size:0.66rem;
    padding:0.06rem 0.45rem; border-radius:5px; line-height:1.6;
}
.ll-pill.hi  { background:var(--ok-bg);   color:var(--ok); }
.ll-pill.mid { background:var(--warn-bg); color:var(--warn); }
.ll-pill.lo  { background:var(--bad-bg);  color:var(--bad); }

.ll-status {
    display:inline-flex; align-items:center; gap:0.45rem;
    font-size:0.8rem; font-weight:500; color:var(--text);
}
.ll-status::before {
    content:""; width:0.52rem; height:0.52rem; border-radius:99px;
    display:inline-block; flex:none;
}
.ll-status.ok::before      { background:var(--ok); }
.ll-status.pending::before { background:var(--warn); }
.ll-status.bad::before     { background:var(--bad); }

/* ---------- banner ---------- */
.ll-banner {
    border-radius:10px; border:1px solid var(--line);
    background:var(--surface);
    border-left:4px solid var(--blue);
    padding:0.7rem 1rem; margin:0.4rem 0 1.1rem;
    font-size:0.92rem; color:var(--text2); line-height:1.6;
}
.ll-banner b { color:var(--text); }
.ll-banner.ok      { border-left-color:var(--ok); }
.ll-banner.pending { border-left-color:var(--warn); }
.ll-banner.bad     { border-left-color:var(--bad); }
.ll-banner.bad b   { color:var(--bad); }
.ll-banner .mono   { font-family:'JetBrains Mono',monospace; font-size:0.85em;
                     color:var(--text); }

/* ---------- tables ---------- */
.ll-table {
    width:100%; border-collapse:separate; border-spacing:0;
    background:var(--surface); border:1px solid var(--line);
    border-radius:10px; overflow:hidden; font-size:0.87rem;
    box-shadow:0 1px 4px var(--shadow);
}
.ll-table th {
    background:var(--surface2); color:var(--text2);
    font-size:0.66rem; font-weight:600; letter-spacing:0.07em;
    text-transform:uppercase; text-align:left; padding:0.5rem 0.8rem;
    border-bottom:1px solid var(--line);
}
.ll-table td {
    color:var(--text); padding:0.48rem 0.8rem;
    border-bottom:1px solid var(--line);
}
.ll-table tbody tr { transition:background .13s ease; }
.ll-table tbody tr:hover { background:var(--surface2); }
.ll-table tr:last-child td { border-bottom:none; }
.ll-table td.num { font-family:'JetBrains Mono',monospace; text-align:right; }
.ll-table td.money { color:var(--green); font-weight:500; }

/* ---------- ledger rows ---------- */
.ll-row-text { font-size:0.87rem; color:var(--text); padding-top:0.35rem; }
.ll-row-text .mono {
    font-family:'JetBrains Mono',monospace; font-size:0.8em; color:var(--text2);
}
.ll-money-cell {
    font-family:'JetBrains Mono',monospace; color:var(--green);
    font-weight:500; font-size:0.87rem; padding-top:0.35rem;
}
.ll-col-head {
    font-size:0.65rem; font-weight:600; letter-spacing:0.07em;
    text-transform:uppercase; color:var(--text2);
}
.ll-detail {
    border:1px solid var(--line); border-left:4px solid var(--violet);
    background:var(--surface); border-radius:12px;
    padding:1rem 1.1rem; margin:0.4rem 0 1rem;
    box-shadow:0 3px 12px var(--shadow);
    animation:rise .3s ease both;
}

/* ---------- buttons ---------- */
.stButton > button {
    border-radius:9px; font-weight:600; font-size:0.86rem;
    transition:transform .14s ease, box-shadow .14s ease;
}
.stButton > button:active { transform:scale(.97); }
.stButton > button[kind="primary"] {
    background:linear-gradient(115deg, var(--red), var(--orange) 60%, var(--amber));
    border:none; color:#ffffff;
    box-shadow:0 3px 10px var(--navglow);
}
.stButton > button[kind="primary"]:hover {
    color:#ffffff; transform:translateY(-1px);
    box-shadow:0 6px 16px var(--navglow);
}
.stButton > button[kind="secondary"] {
    background:var(--surface); border:1px solid var(--line); color:var(--text);
}
.stButton > button[kind="secondary"]:hover {
    border-color:var(--orange); color:var(--orange); transform:translateY(-1px);
}

/* ---------- widgets: keep text readable in BOTH modes ---------- */
[data-testid="stFileUploaderDropzone"] {
    background:var(--surface); border:1.5px dashed var(--line);
    border-radius:12px; transition:border-color .2s ease;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color:var(--teal); }
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] div { color:var(--text2); }
[data-testid="stFileUploaderDropzone"] button {
    color:var(--text); border:1px solid var(--line); background:var(--surface2);
}
[data-testid="stExpander"] {
    background:var(--surface); border:1px solid var(--line);
    border-radius:12px; box-shadow:0 2px 8px var(--shadow);
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary * { color:var(--text) !important; font-weight:600; }
.stTextInput input {
    background:var(--surface); color:var(--text);
    border:1px solid var(--line); border-radius:9px;
}
.stTextInput input:focus { border-color:var(--blue); }
.stTextInput label { color:var(--text2) !important; font-size:0.78rem; }
.stSpinner > div { color:var(--text2); }
[data-testid="stImageCaption"] { color:var(--text2) !important; }

.ll-doc-img {
    max-height:420px; width:auto; max-width:100%;
    border:1px solid var(--line); border-radius:12px;
    box-shadow:0 4px 14px var(--shadow); display:block;
}
</style>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Constants + helpers
# --------------------------------------------------------------------------- #
MONEY_FIELDS = {"subtotal", "tax", "discount", "additional_charges", "total"}
SCALAR_FIELDS = [
    "vendor", "invoice_number", "date", "currency",
    "subtotal", "tax", "discount", "additional_charges", "total",
]
STATUS_META = {
    "auto_approved": ("ok", "auto-approved"),
    "approved": ("ok", "approved"),
    "pending_review": ("pending", "pending review"),
    "blocked": ("bad", "blocked"),
    "rejected": ("bad", "rejected"),
}
PAGES = [("home", "Home"), ("upload", "Upload"),
         ("review", "Review"), ("ledger", "Ledger")]
CARD_HUES = ["var(--red)", "var(--orange)", "var(--amber)", "var(--green)",
             "var(--teal)", "var(--blue)", "var(--violet)"]


@st.cache_data(ttl=5, show_spinner=False)
def fetch(path: str):
    return requests.get(f"{API}{path}", timeout=30).json()


def esc(v) -> str:
    return html_lib.escape(str(v))


def pill(c: float) -> str:
    tier = "hi" if c >= 0.9 else ("mid" if c >= 0.75 else "lo")
    return f'<span class="ll-pill {tier}">{c:.2f}</span>'


def status_chip(status: str) -> str:
    kind, label = STATUS_META.get(status, ("pending", status))
    return f'<span class="ll-status {kind}">{label}</span>'


def field_card(label: str, value, conf=None, money=False, hue=None) -> str:
    shown = esc(value) if value not in ("", None) else "-"
    money_cls = " money" if money and shown != "-" else ""
    conf_html = pill(conf) if conf is not None else ""
    hue_style = f' style="--kc:{hue};"' if hue else ""
    return (
        f'<div class="ll-field"{hue_style}>'
        f'<div class="ll-field-label"><span>{esc(label)}</span>{conf_html}</div>'
        f'<div class="ll-field-value{money_cls}" title="{shown}">{shown}</div>'
        f"</div>"
    )


def html_table(headers, rows) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = ""
    for row in rows:
        cells = "".join(f'<td class="{cls}">{txt}</td>' for txt, cls in row)
        body += f"<tr>{cells}</tr>"
    return (
        f'<table class="ll-table"><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table>"
    )


def render_extraction(extraction: dict):
    cols = st.columns(3)
    for i, name in enumerate(SCALAR_FIELDS):
        node = extraction[name]
        with cols[i % 3]:
            st.markdown(
                field_card(
                    name.replace("_", " ").title(),
                    node["value"], node["confidence"],
                    name in MONEY_FIELDS,
                    hue=CARD_HUES[i % len(CARD_HUES)],
                ),
                unsafe_allow_html=True,
            )
    items = extraction.get("line_items") or []
    if items:
        st.markdown('<div class="ll-rule">Line items</div>', unsafe_allow_html=True)
        rows = [
            [
                (esc(it["description"]), ""),
                (f"{it['quantity']:.0f}", "num"),
                (f"{it['unit_price']:,.2f}", "num"),
                (f"{it['amount']:,.2f}", "num money"),
                (pill(it["confidence"]), "num"),
            ]
            for it in items
        ]
        st.markdown(
            html_table(["Description", "Qty", "Unit price", "Amount", "Confidence"], rows),
            unsafe_allow_html=True,
        )


def render_flagged(flagged: list):
    st.markdown('<div class="ll-rule">Held for review</div>', unsafe_allow_html=True)
    rows = [
        [(esc(f["field_path"]), ""), (esc(f["value"]), "num"),
         (pill(f["confidence"]), "num")]
        for f in flagged
    ]
    st.markdown(
        html_table(["Field", "Extracted value", "Confidence"], rows),
        unsafe_allow_html=True,
    )


def banner(kind: str, inner: str):
    st.markdown(f'<div class="ll-banner {kind}">{inner}</div>', unsafe_allow_html=True)


def page_title(title_html: str, sub: str):
    st.markdown(
        f'<div class="ll-page-title rise">{title_html}</div>'
        f'<div class="ll-page-sub rise-1">{sub}</div>',
        unsafe_allow_html=True,
    )


def goto(page: str):
    st.session_state.page = page
    st.rerun()


# --------------------------------------------------------------------------- #
# Fixed top navigation
# --------------------------------------------------------------------------- #
with st.container(key="topnav"):
    brand_col, nav_col, theme_col = st.columns([2.1, 4.0, 0.55], gap="small")
    with brand_col:
        st.markdown('<div class="ll-wordmark">LedgerLens</div>',
                    unsafe_allow_html=True)
    with nav_col:
        nav_cols = st.columns(len(PAGES))
        for (slug, label), col in zip(PAGES, nav_cols):
            with col:
                if st.button(
                    label,
                    key=f"nav_{slug}",
                    use_container_width=True,
                    type="primary" if st.session_state.page == slug else "secondary",
                ):
                    goto(slug)
    with theme_col:
        with st.container(key="themebtn"):
            if st.button("☀" if DARK else "☾", key="theme_toggle",
                         help="Switch light and dark"):
                st.session_state.theme = "light" if DARK else "dark"
                st.rerun()


# --------------------------------------------------------------------------- #
# PAGE: Home
# --------------------------------------------------------------------------- #
def page_home():
    st.markdown(
        """
<div class="ll-hero rise">
  <h1>Every receipt, <span class="c1">read</span> and
  <span class="c2">reconciled</span>.</h1>
  <div class="ink"></div>
  <p>Hand it a photo. A crumpled shop receipt, a formal invoice, anything.
  It reads every field, says how sure it is about each one, and asks a
  person whenever it isn&rsquo;t.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1.35, 1, 1.35])
    with mid:
        if st.button("Extract a document", type="primary",
                     use_container_width=True):
            goto("upload")

    st.markdown('<div class="ll-rule">What makes it careful</div>',
                unsafe_allow_html=True)
    f1, f2, f3 = st.columns(3, gap="medium")
    with f1:
        st.markdown(
            '<div class="ll-feature rise-1" style="--fc:var(--red);">'
            "<h4>A strict contract</h4>"
            "<p>The model must fill a fixed schema: typed amounts, ISO dates, "
            "real currency codes. Anything malformed fails loudly instead of "
            "slipping into your records.</p></div>",
            unsafe_allow_html=True,
        )
    with f2:
        st.markdown(
            '<div class="ll-feature rise-2" style="--fc:var(--teal);">'
            "<h4>Honest about doubt</h4>"
            "<p>Every field carries its own confidence score, and the arithmetic "
            "is checked independently. Subtotal, tax, charges and discounts "
            "must actually add up to the total.</p></div>",
            unsafe_allow_html=True,
        )
    with f3:
        st.markdown(
            '<div class="ll-feature rise-3" style="--fc:var(--violet);">'
            "<h4>A person has the last word</h4>"
            "<p>Uncertain documents wait in a queue with the original image "
            "beside the numbers. You correct, approve, or reject. Nothing "
            "is accepted silently.</p></div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="ll-rule">The path a document takes</div>',
                unsafe_allow_html=True)
    steps = [
        ("01", "var(--red)", "Screened",
         "Each upload passes a moderation gate before any model sees it."),
        ("02", "var(--orange)", "Read",
         "A vision model transcribes the image into the invoice schema, field by field."),
        ("03", "var(--teal)", "Weighed",
         "Low confidence or sums that do not close send it to review; clean documents approve themselves."),
        ("04", "var(--violet)", "Kept",
         "The image is stamped with its document id and time, then filed in the ledger."),
    ]
    for n, hue, t, d in steps:
        st.markdown(
            f'<div class="ll-step" style="--sc:{hue};"><span class="n">{n}</span>'
            f'<span><span class="t">{t}</span><br/>'
            f'<span class="d">{d}</span></span></div>',
            unsafe_allow_html=True,
        )

    try:
        docs = fetch("/documents")
    except requests.RequestException:
        docs = None
    if docs:
        st.markdown('<div class="ll-rule">At the moment</div>',
                    unsafe_allow_html=True)
        df = pd.DataFrame(docs)
        pending = int((df["status"] == "pending_review").sum())
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.markdown(field_card("Documents processed", len(df),
                                   hue="var(--blue)"),
                        unsafe_allow_html=True)
        with s2:
            st.markdown(field_card("Awaiting review", pending,
                                   hue="var(--amber)"),
                        unsafe_allow_html=True)
        with s3:
            st.markdown(
                field_card("Auto-approval rate",
                           f"{(df['status'] == 'auto_approved').mean() * 100:.0f}%",
                           hue="var(--teal)"),
                unsafe_allow_html=True,
            )
        with s4:
            st.markdown(
                field_card("Total spend", f"${df['cost_usd'].sum():.4f}",
                           None, True, hue="var(--green)"),
                unsafe_allow_html=True,
            )
        if pending:
            _, mid, _ = st.columns([1.35, 1, 1.35])
            with mid:
                if st.button(f"Review {pending} waiting",
                             use_container_width=True):
                    goto("review")


# --------------------------------------------------------------------------- #
# PAGE: Upload
# --------------------------------------------------------------------------- #
def page_upload():
    page_title(
        'Extract a <span class="c1">document</span>',
        "JPG or PNG. It will be screened, read, and routed in one pass.",
    )
    uploaded = st.file_uploader(
        "Drop a receipt or invoice", type=["jpg", "jpeg", "png"]
    )

    if uploaded is None:
        banner(
            "pending",
            "Flat, well-lit photos tend to approve themselves. A blurry or "
            "crumpled one is a good way to watch the review queue earn its keep.",
        )
        return

    col_img, col_data = st.columns([1, 2], gap="large")
    with col_img:
        st.image(uploaded, caption=uploaded.name, use_container_width=True)
        extract_clicked = st.button(
            "Extract", type="primary", use_container_width=True
        )

    if not extract_clicked:
        return

    with st.spinner("Screening, reading, weighing…"):
        try:
            resp = requests.post(
                f"{API}/ingest",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                timeout=120,
            )
        except requests.RequestException as e:
            st.error(f"API unreachable: {e}")
            st.stop()
    st.cache_data.clear()

    with col_data:
        if resp.status_code == 422:
            detail = resp.json().get("detail", {})
            banner(
                "bad",
                f"<b>Blocked at the gate</b>: "
                f"{esc(detail.get('blocked_reason', 'flagged'))}",
            )
        elif resp.status_code != 200:
            banner("bad", f"Error {resp.status_code}: {esc(resp.text)}")
        else:
            data = resp.json()
            if data["status"] == "auto_approved":
                banner(
                    "ok",
                    f"<b>Approved itself.</b> Every field cleared the threshold. "
                    f"Doc <span class='mono'>{data['doc_id']}</span>"
                    f" · <span class='mono'>${data['cost_usd']:.5f}</span>",
                )
            else:
                n = len(data["flagged_fields"])
                banner(
                    "pending",
                    f"<b>{n} field{'s' if n != 1 else ''} held back</b>, "
                    f"waiting in the review queue. "
                    f"Doc <span class='mono'>{data['doc_id']}</span>"
                    f" · <span class='mono'>${data['cost_usd']:.5f}</span>",
                )
            render_extraction(data["extraction"])
            if data["flagged_fields"]:
                render_flagged(data["flagged_fields"])


# --------------------------------------------------------------------------- #
# PAGE: Review
# --------------------------------------------------------------------------- #
def page_review():
    top_l, top_r = st.columns([6, 1])
    with top_l:
        page_title(
            'Review <span class="c1">queue</span>',
            "Documents the model was not sure about, oldest first. "
            "Fix what needs fixing, then approve or reject.",
        )
    with top_r:
        if st.button("Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    try:
        queue = fetch("/review")
    except requests.RequestException as e:
        st.error(f"API unreachable: {e}")
        queue = []

    if not queue:
        banner("ok", "The queue is empty. Nothing needs a person right now.")
        return

    st.markdown(
        f'<span class="ll-status pending">{len(queue)} document'
        f'{"s" if len(queue) != 1 else ""} waiting</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    for item in queue:
        n_flags = len(item["flagged_fields"])
        with st.expander(
            f"{item['filename']}  ·  {item['doc_id']}  ·  "
            f"{n_flags} field{'s' if n_flags != 1 else ''} held",
            expanded=len(queue) == 1,
        ):
            col_img, col_fields = st.columns([1, 2], gap="large")
            with col_img:
                st.markdown(
                    f'<img class="ll-doc-img" '
                    f'src="{API}{item["watermarked_image_url"]}"/>',
                    unsafe_allow_html=True,
                )
            with col_fields:
                render_extraction(item["extraction"])

            st.markdown(
                '<div class="ll-rule">Correct the held fields</div>',
                unsafe_allow_html=True,
            )
            df = pd.DataFrame(item["flagged_fields"])
            df["corrected_value"] = df["value"]
            edited = st.data_editor(
                df,
                column_config={
                    "field_path": st.column_config.TextColumn("Field", disabled=True),
                    "value": st.column_config.TextColumn("Extracted", disabled=True),
                    "confidence": st.column_config.NumberColumn(
                        "Conf.", disabled=True, format="%.2f"
                    ),
                    "corrected_value": st.column_config.TextColumn("Corrected value"),
                },
                hide_index=True,
                use_container_width=True,
                key=f"editor_{item['doc_id']}",
            )

            reject_reason = st.text_input(
                "Reason, if rejecting",
                value="Not a valid receipt/invoice",
                key=f"reason_{item['doc_id']}",
            )
            col_ok, col_no, _ = st.columns([1, 1, 2])
            with col_ok:
                approve_clicked = st.button(
                    "Approve", key=f"approve_{item['doc_id']}",
                    type="primary", use_container_width=True,
                )
            with col_no:
                reject_clicked = st.button(
                    "Reject", key=f"reject_{item['doc_id']}",
                    use_container_width=True,
                )

            if reject_clicked:
                r = requests.post(
                    f"{API}/reject",
                    json={"doc_id": item["doc_id"], "reason": reject_reason},
                    timeout=30,
                )
                if r.status_code == 200:
                    st.toast("Rejected.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Reject failed: {r.text}")

            if approve_clicked:
                corrections = [
                    {"field_path": row["field_path"],
                     "corrected_value": str(row["corrected_value"])}
                    for _, row in edited.iterrows()
                    if str(row["corrected_value"]) != str(row["value"])
                ]
                r = requests.post(
                    f"{API}/approve",
                    json={"doc_id": item["doc_id"], "corrections": corrections},
                    timeout=30,
                )
                if r.status_code == 200:
                    n = r.json()["applied_corrections"]
                    st.toast(f"Approved, {n} correction{'s' if n != 1 else ''}.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Approve failed: {r.text}")


# --------------------------------------------------------------------------- #
# PAGE: Ledger
# --------------------------------------------------------------------------- #
def page_ledger():
    page_title(
        'The <span class="c1">ledger</span>',
        "Every document that has passed through, newest first. "
        "Open a row for its stamped image and summary.",
    )

    try:
        docs = fetch("/documents")
    except requests.RequestException as e:
        st.error(f"API unreachable: {e}")
        docs = []

    if not docs:
        banner("pending", "Nothing here yet. The ledger fills as you upload.")
        return

    df = pd.DataFrame(docs)
    n_auto = int((df["status"] == "auto_approved").sum())
    n_appr = int((df["status"] == "approved").sum())
    n_pend = int((df["status"] == "pending_review").sum())
    n_rej = int(df["status"].isin(["rejected", "blocked"]).sum())
    spend = df["cost_usd"].sum()

    s1, s2, s3, s4, s5 = st.columns(5)
    for col, label, val, money, hue in (
        (s1, "Auto-approved", n_auto, False, "var(--teal)"),
        (s2, "Approved", n_appr, False, "var(--green)"),
        (s3, "Pending review", n_pend, False, "var(--amber)"),
        (s4, "Rejected / blocked", n_rej, False, "var(--red)"),
        (s5, "Total spend", f"${spend:.4f}", True, "var(--violet)"),
    ):
        with col:
            st.markdown(field_card(label, val, None, money, hue=hue),
                        unsafe_allow_html=True)

    st.markdown('<div class="ll-rule">All documents</div>',
                unsafe_allow_html=True)

    h = st.columns([2.6, 2.0, 1.7, 1.3, 1.4, 0.9])
    for c, t in zip(h, ("File", "Status", "Vendor", "Total", "Ingested", "")):
        c.markdown(f'<span class="ll-col-head">{t}</span>',
                   unsafe_allow_html=True)

    for d in docs:
        c1, c2, c3, c4, c5, c6 = st.columns([2.6, 2.0, 1.7, 1.3, 1.4, 0.9])
        with c1:
            st.markdown(
                f'<div class="ll-row-text">{esc(d["filename"])}<br/>'
                f'<span class="mono">{esc(d["doc_id"])}</span></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(status_chip(d["status"]), unsafe_allow_html=True)
        with c3:
            st.markdown(
                f'<div class="ll-row-text">{esc(d.get("vendor") or "-")}</div>',
                unsafe_allow_html=True,
            )
        with c4:
            total = d.get("total")
            shown = f"{total:,.2f}" if isinstance(total, (int, float)) else "-"
            st.markdown(f'<div class="ll-money-cell">{shown}</div>',
                        unsafe_allow_html=True)
        with c5:
            ts = str(d.get("created_at", ""))[:16].replace("T", " · ")
            st.markdown(
                f'<div class="ll-row-text"><span class="mono">{esc(ts)}</span></div>',
                unsafe_allow_html=True,
            )
        with c6:
            is_open = st.session_state.open_doc == d["doc_id"]
            if st.button(
                "Close" if is_open else "Open",
                key=f"open_{d['doc_id']}",
                use_container_width=True,
                type="primary" if is_open else "secondary",
            ):
                st.session_state.open_doc = None if is_open else d["doc_id"]
                st.rerun()

        if st.session_state.open_doc == d["doc_id"]:
            st.markdown('<div class="ll-detail">', unsafe_allow_html=True)
            di, dm = st.columns([1.3, 1], gap="large")
            with di:
                st.markdown(
                    f'<img class="ll-doc-img" src="{API}/image/{d["doc_id"]}"/>',
                    unsafe_allow_html=True,
                )
                st.caption("Stamped with its document id and UTC time, lower right.")
            with dm:
                total = d.get("total")
                st.markdown(
                    field_card("Vendor", d.get("vendor") or "-",
                               hue="var(--blue)")
                    + field_card(
                        "Total",
                        f"{total:,.2f}" if isinstance(total, (int, float)) else "-",
                        None, True, hue="var(--green)",
                    )
                    + field_card("Currency", d.get("currency") or "-",
                                 hue="var(--teal)")
                    + field_card("Cost", f"${d.get('cost_usd', 0):.5f}",
                                 None, True, hue="var(--violet)"),
                    unsafe_allow_html=True,
                )
                st.markdown(status_chip(d["status"]), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
{"home": page_home, "upload": page_upload,
 "review": page_review, "ledger": page_ledger}[st.session_state.page]()