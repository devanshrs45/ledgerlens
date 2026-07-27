#THIS FILE IS UNUSED. USING HTML/CSS/JS INSTEAD OF STREAMLIT UI. 

'''

import html as html_lib
import os
import pandas as pd
import requests
import streamlit as st

#API = os.getenv("API_BASE_URL", "http://localhost:8000")   Not using streamlit anymore

st.set_page_config(
    page_title="OnRecord - receipts and invoices",
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

# Shared colors for light and dark mode.
LIGHT_VARS = """
    --bg:#f7f3ea; --surface:#fffdf8; --surface2:#f1eadf; --surface3:#faf7f0;
    --line:#d9d1c4; --line-strong:#b9ae9f;
    --text:#222a30; --text2:#626b70; --text3:#8a9093;
    --red:#c84c43; --orange:#d96b3c; --amber:#9b751c; --green:#34785b;
    --teal:#248877; --blue:#356aa5; --violet:#725c84;
    --accent:#c74235; --accent-hover:#b93b30; --accent-soft:#f6e1dd;
    --yellow:#f0c95d;
    --ok:#2f7652; --ok-bg:#e2efe7; --warn:#866117; --warn-bg:#f4ebcf;
    --bad:#aa4138; --bad-bg:#f6e2dd;
    --wash-a:rgba(240,201,93,.16); --wash-b:rgba(36,136,119,.10);
    --notebook-line:rgba(53,106,165,.15); --notebook-margin:rgba(228,95,79,.24);
    --nav-bg:rgba(255,253,248,.98); --nav-line:#d9d1c4; --nav-shadow:rgba(54,44,32,.10);
    --nav-text:#222a30; --nav-muted:#687177; --nav-hover:#f1eadf;
    --theme-bg:#25313a; --theme-text:#ffffff; --theme-border:#25313a;
    --theme-hover-bg:#c74235; --theme-hover-text:#ffffff; --theme-hover-border:#c74235;
    --focus:rgba(53,106,165,.36);
    --button-text:#ffffff; --accent-text:#ffffff; --button-shadow:#76271f; --panel-shadow:#e2d7c7;
    --receipt-bg:#fffdf3; --receipt-ink:#273039; --receipt-muted:#77746d;
    --receipt-line:#a99f91; --receipt-shadow:#dfd3bf;
"""
DARK_VARS = """
    --bg:#0f1820; --surface:#17242d; --surface2:#20313c; --surface3:#132029;
    --line:#314753; --line-strong:#4a6472;
    --text:#f5f1e8; --text2:#bdc7cb; --text3:#88979e;
    --red:#ff8e82; --orange:#f7a067; --amber:#e5bd57; --green:#7bc99b;
    --teal:#62c9b7; --blue:#8eb6f2; --violet:#c6a5d5;
    --accent:#ff806c; --accent-hover:#ff947f; --accent-soft:#352927;
    --yellow:#f1c75b;
    --ok:#86d0a5; --ok-bg:#213a30; --warn:#f0cb6b; --warn-bg:#3b321d;
    --bad:#ff9688; --bad-bg:#412a29;
    --wash-a:rgba(241,199,91,.07); --wash-b:rgba(98,201,183,.06);
    --notebook-line:rgba(142,182,242,.13); --notebook-margin:rgba(255,128,108,.20);
    --nav-bg:rgba(16,27,36,.98); --nav-line:#314753; --nav-shadow:rgba(0,0,0,.30);
    --nav-text:#f5f1e8; --nav-muted:#aebbc1; --nav-hover:#20313c;
    --theme-bg:#f3e5c8; --theme-text:#18242d; --theme-border:#f3e5c8;
    --theme-hover-bg:#f1c75b; --theme-hover-text:#18242d; --theme-hover-border:#f1c75b;
    --focus:rgba(142,182,242,.42);
    --button-text:#18242d; --accent-text:#18242d; --button-shadow:#75382f; --panel-shadow:#091117;
    --receipt-bg:#f5efdf; --receipt-ink:#273039; --receipt-muted:#77746d;
    --receipt-line:#a99f91; --receipt-shadow:#0a1117;
"""

st.markdown(
    f"<style>:root {{{DARK_VARS if DARK else LIGHT_VARS} color-scheme:{'dark' if DARK else 'light'};}}</style>",
    unsafe_allow_html=True,
)

# Main stylesheet.
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Source+Sans+3:wght@400;500;600;700&display=swap');

[data-testid="stToolbar"], [data-testid="stHeader"],
[data-testid="stDecoration"], footer, #MainMenu { display:none !important; }

html, body, [class*="css"] { font-family:'Source Sans 3',system-ui,sans-serif; }
body { overflow-x:hidden; }
*, *::before, *::after { box-sizing:border-box; }
.stApp {
    color:var(--text);
    background:
      radial-gradient(circle at 92% 8%, var(--wash-a) 0 10rem, transparent 10.1rem),
      radial-gradient(circle at 7% 92%, var(--wash-b) 0 12rem, transparent 12.1rem),
      var(--bg);
    transition:background .2s ease, color .2s ease;
}
.block-container { max-width:1120px; padding-top:5.7rem; padding-bottom:4rem; }
h1,h2,h3,h4,p,li,label,.stMarkdown { color:var(--text); }
small,.stCaption,[data-testid="stCaptionContainer"] { color:var(--text2) !important; }
a { color:var(--blue); }

@keyframes enter {
    from { opacity:0; transform:translateY(8px); }
    to { opacity:1; transform:translateY(0); }
}
@keyframes receipt-in {
    from { opacity:0; transform:translateY(12px) rotate(3deg); }
    to { opacity:1; transform:rotate(1deg); }
}
.rise { animation:enter .28s ease both; }
.rise-1 { animation:enter .28s .05s ease both; }
.rise-2 { animation:enter .28s .1s ease both; }
.rise-3 { animation:enter .28s .15s ease both; }

/* Full width navigation. No floating rounded shell. */
.st-key-topnav {
    position:fixed; inset:0 0 auto 0; z-index:9999;
    width:100%;
    padding:.62rem max(1rem, calc((100vw - 1120px) / 2));
    background:var(--nav-bg);
    border:0; border-bottom:1px solid var(--nav-line);
    border-radius:0;
    box-shadow:0 4px 16px var(--nav-shadow);
}
.st-key-topnav::before {
    content:""; position:absolute; inset:0 0 auto; height:3px;
    background:linear-gradient(90deg,var(--accent) 0 34%,var(--yellow) 34% 62%,var(--teal) 62% 100%);
}
.ll-wordmark {
    display:flex; align-items:center; gap:.55rem;
    min-height:2.35rem;
    color:var(--nav-text); font-size:1.08rem; font-weight:700;
    letter-spacing:-.02em;
}
.ll-mark {
    display:grid; place-items:center;
    width:1.8rem; height:1.8rem;
    background:var(--accent); color:var(--accent-text);
    border-radius:50% 50% 45% 55%;
    font-family:Georgia,serif; font-size:.74rem; font-weight:700;
    transform:rotate(-5deg);
}
.st-key-topnav .stButton > button {
    min-height:2.3rem !important; padding:.3rem .45rem !important;
    border:0 !important; border-radius:3px !important;
    background:transparent !important; box-shadow:none !important;
    color:var(--nav-muted) !important;
    font-size:.84rem !important; font-weight:600 !important;
    transform:none !important;
}
.st-key-topnav .stButton > button *,
.st-key-topnav .stButton > button p,
.st-key-topnav .stButton > button span,
.st-key-topnav .stButton > button div { color:inherit !important; }
.st-key-topnav .stButton > button:hover {
    background:var(--nav-hover) !important;
    color:var(--nav-text) !important;
}
.st-key-topnav .stButton > button[kind="primary"] {
    color:var(--nav-text) !important;
    background:transparent !important;
    box-shadow:inset 0 -3px 0 var(--accent) !important;
}
.st-key-themebtn .stButton > button,
.st-key-topnav .st-key-themebtn .stButton > button {
    width:100% !important; min-width:5.8rem !important;
    min-height:2.3rem !important; height:2.3rem !important;
    padding:0 .65rem !important;
    border:2px solid var(--theme-border) !important;
    border-radius:5px !important;
    background:var(--theme-bg) !important;
    color:var(--theme-text) !important;
    font-size:.78rem !important; font-weight:700 !important;
    box-shadow:none !important;
}
.st-key-themebtn .stButton > button *,
.st-key-themebtn .stButton > button p,
.st-key-themebtn .stButton > button span,
.st-key-themebtn .stButton > button div,
.st-key-topnav .st-key-themebtn .stButton > button * {
    color:var(--theme-text) !important;
    fill:var(--theme-text) !important;
}
.st-key-themebtn .stButton > button:hover,
.st-key-topnav .st-key-themebtn .stButton > button:hover {
    border-color:var(--theme-hover-border) !important;
    background:var(--theme-hover-bg) !important;
    color:var(--theme-hover-text) !important;
}
.st-key-themebtn .stButton > button:hover *,
.st-key-themebtn .stButton > button:hover p,
.st-key-themebtn .stButton > button:hover span,
.st-key-themebtn .stButton > button:hover div,
.st-key-topnav .st-key-themebtn .stButton > button:hover * {
    color:var(--theme-hover-text) !important;
    fill:var(--theme-hover-text) !important;
}
.st-key-themebtn .stButton > button:focus-visible {
    outline:3px solid var(--focus) !important; outline-offset:2px !important;
}

/* Home. Notebook lines sit behind the content, not inside a card. */
.st-key-home_hero {
    position:relative; min-height:430px;
    padding:3.8rem 1rem 3rem 3.8rem;
    overflow:hidden;
}
.st-key-home_hero::before {
    content:""; position:absolute; inset:.5rem 0 .35rem;
    background:
      linear-gradient(90deg,transparent 0 2.6rem,var(--notebook-margin) 2.6rem 2.68rem,transparent 2.68rem),
      repeating-linear-gradient(to bottom,transparent 0 36px,var(--notebook-line) 36px 37px);
    opacity:.88;
    -webkit-mask-image:linear-gradient(90deg,#000 0 84%,transparent 100%);
    mask-image:linear-gradient(90deg,#000 0 84%,transparent 100%);
    pointer-events:none;
}
.st-key-home_hero [data-testid="stHorizontalBlock"] {
    position:relative; z-index:1; align-items:center;
}
.ll-home-copy { max-width:660px; }
.ll-home-copy h1 {
    margin:0 0 .8rem;
    font-family:Georgia,'Times New Roman',serif;
    font-size:clamp(3.15rem,6.4vw,5.15rem);
    line-height:.98; letter-spacing:-.045em; font-weight:700;
}
.ll-home-copy h1 span {
    position:relative; display:inline-block; color:var(--accent);
}
.ll-home-copy h1 span::after {
    content:""; position:absolute; left:0; right:-.05em; bottom:-.08em;
    height:6px; background:var(--yellow); opacity:.8;
    transform:rotate(-1deg); z-index:-1;
}
.ll-home-copy h2 {
    max-width:560px; margin:0 0 1.45rem;
    color:var(--text2); font-size:clamp(1.02rem,1.7vw,1.18rem);
    line-height:1.55; font-weight:500;
}
.st-key-home_hero .stButton > button { max-width:220px; min-height:2.75rem; }
.ll-receipt-wrap {
    position:relative; width:min(100%,300px); margin:0 auto;
    animation:receipt-in .4s .08s ease both;
}
.ll-receipt-pin {
    position:absolute; z-index:4; top:-.45rem; left:50%;
    width:1rem; height:1rem; border-radius:50%;
    background:var(--yellow); border:3px solid var(--receipt-ink);
    box-shadow:0 4px 0 var(--receipt-shadow);
}
.ll-home-receipt {
    position:relative; padding:2rem 1.45rem 2.2rem;
    color:var(--receipt-ink);
    background:
      repeating-linear-gradient(to bottom,transparent 0 27px,rgba(38,48,58,.08) 27px 28px),
      var(--receipt-bg);
    border:1px solid var(--receipt-line);
    border-radius:2px;
    clip-path:polygon(0 0,100% 0,100% 96%,96% 100%,91% 96%,86% 100%,81% 96%,76% 100%,71% 96%,66% 100%,61% 96%,56% 100%,51% 96%,46% 100%,41% 96%,36% 100%,31% 96%,26% 100%,21% 96%,16% 100%,11% 96%,6% 100%,0 96%);
    box-shadow:12px 14px 0 var(--receipt-shadow);
    transform:rotate(1deg);
    transition:transform .18s ease;
}
.ll-home-receipt:hover { transform:rotate(-.4deg) translateY(-3px); }
.ll-home-receipt::before {
    content:""; position:absolute; left:1.2rem; right:1.2rem; top:.95rem;
    border-top:2px dashed var(--receipt-line);
}
.ll-receipt-store { margin:.25rem 0 .15rem; color:var(--receipt-ink); font-size:1.2rem; font-weight:700; }
.ll-receipt-meta { margin-bottom:.95rem; color:var(--receipt-muted); font-size:.75rem; }
.ll-receipt-line { display:grid; grid-template-columns:1fr auto; gap:.8rem; padding:.31rem 0; color:var(--receipt-ink); font-size:.8rem; }
.ll-receipt-line span:last-child,.ll-receipt-total span:last-child { font-family:'DM Mono',monospace; }
.ll-receipt-total { display:flex; justify-content:space-between; margin-top:.7rem; padding-top:.62rem; border-top:2px solid var(--receipt-ink); color:var(--receipt-ink); font-weight:700; }
.ll-receipt-note { position:absolute; right:.8rem; bottom:1.25rem; color:#b64035; font-family:'Comic Sans MS','Bradley Hand',cursive; font-size:.9rem; transform:rotate(-6deg); }
.ll-home-stats {
    display:grid; grid-template-columns:repeat(3,1fr);
    margin:.4rem 0 1.7rem; padding:0;
    border-top:1px solid var(--line); border-bottom:1px solid var(--line);
}
.ll-home-stat { position:relative; padding:1.05rem 1.15rem; border-right:1px solid var(--line); }
.ll-home-stat:last-child { border-right:0; }
.ll-home-stat::before { content:""; position:absolute; top:-3px; left:1.15rem; width:2.7rem; height:5px; background:var(--stat-color,var(--accent)); }
.ll-home-stat .value { display:block; color:var(--text); font-size:1.85rem; line-height:1.1; font-weight:700; }
.ll-home-stat .label { color:var(--text2); font-size:.82rem; }

/* Plain page headings */
.ll-page-head { margin:1rem 0 1.55rem; }
.ll-page-title { margin:0 0 .25rem; color:var(--text); font-family:Georgia,'Times New Roman',serif; font-size:clamp(2rem,4vw,2.65rem); line-height:1.08; letter-spacing:-.03em; font-weight:700; }
.ll-page-sub { max-width:660px; color:var(--text2); font-size:.95rem; line-height:1.5; }
.ll-rule { display:flex; align-items:center; gap:.7rem; margin:1.5rem 0 .75rem; color:var(--text2); font-size:.72rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase; }
.ll-rule::after { content:""; flex:1; border-top:1px dashed var(--line-strong); }

/* Upload workspace uses a folder shape instead of a rounded card. */
.st-key-upload_workspace {
    position:relative; margin-top:2.3rem; padding:1.35rem;
    background:var(--surface); border:1px solid var(--line-strong);
    border-radius:0 16px 16px 16px;
    box-shadow:8px 10px 0 var(--panel-shadow);
}
.st-key-upload_workspace::before {
    content:"Upload"; position:absolute; left:-1px; top:-2.15rem;
    min-width:7rem; padding:.5rem 1rem .45rem;
    background:var(--surface); border:1px solid var(--line-strong); border-bottom:0;
    border-radius:9px 9px 0 0;
    color:var(--text); font-size:.75rem; font-weight:700; letter-spacing:.04em;
}
.ll-upload-copy { padding:.2rem 0 .6rem; }
.ll-upload-copy h3 { margin:0 0 .2rem; font-size:1.15rem; font-weight:700; }
.ll-upload-copy p { margin:0; color:var(--text2); font-size:.87rem; }
.ll-upload-help { display:flex; flex-wrap:wrap; gap:.4rem 1rem; margin:.7rem 0 .9rem; color:var(--text2); font-size:.75rem; }
.ll-upload-help span::before { content:""; display:inline-block; width:.42rem; height:.42rem; margin-right:.38rem; border-radius:50%; background:var(--accent); vertical-align:.05rem; }
.ll-empty-preview { min-height:315px; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:2rem; text-align:center; border-left:1px dashed var(--line-strong); background:repeating-linear-gradient(to bottom,transparent 0 31px,var(--notebook-line) 31px 32px); }
.ll-empty-icon { position:relative; width:4rem; height:5.1rem; margin-bottom:.9rem; border:1.5px solid var(--line-strong); background:var(--surface2); transform:rotate(-2deg); }
.ll-empty-icon::before { content:""; position:absolute; inset:1rem .65rem auto; height:1px; background:var(--line-strong); box-shadow:0 .75rem 0 var(--line-strong),0 1.5rem 0 var(--line-strong),0 2.25rem 0 var(--line-strong); }
.ll-empty-icon::after { content:"+"; position:absolute; display:grid; place-items:center; right:-.65rem; bottom:-.55rem; width:1.8rem; height:1.8rem; border-radius:50%; background:var(--accent); color:var(--accent-text); font-size:1.1rem; font-weight:700; }
.ll-empty-preview b { font-size:.9rem; }
.ll-empty-preview p { margin:.2rem 0 0; color:var(--text2); font-size:.78rem; }
.st-key-preview_card { padding:.25rem 0 .1rem 1.15rem; border-left:1px dashed var(--line-strong); }
.ll-file-meta { display:flex; justify-content:space-between; gap:.75rem; padding:.5rem .1rem 0; color:var(--text2); font-size:.72rem; }
.st-key-upload_workspace [data-testid="stImage"] img { max-height:360px; object-fit:contain; border:1px solid var(--line); border-radius:2px; box-shadow:7px 8px 0 var(--panel-shadow); }
.st-key-upload_workspace .stButton > button { min-height:2.7rem; }

/* One extraction sheet, not a group of separate cards. */
.ll-field-grid {
    display:grid; grid-template-columns:repeat(3,minmax(0,1fr));
    overflow:hidden; margin:.4rem 0 1rem;
    background:var(--surface); border:1px solid var(--line-strong);
    border-radius:3px 15px 3px 15px;
}
.ll-field-grid-single { grid-template-columns:1fr; margin-top:.2rem; }
.ll-field {
    position:relative; min-width:0; min-height:76px;
    padding:.78rem .85rem .68rem 1rem;
    border-right:1px solid var(--line); border-bottom:1px solid var(--line);
    background:transparent;
    transition:background .14s ease;
}
.ll-field:nth-child(3n) { border-right:0; }
.ll-field::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--kc,var(--accent)); opacity:.8; }
.ll-field:hover { background:var(--surface2); }
.ll-field-label { display:flex; justify-content:space-between; align-items:center; gap:.4rem; margin-bottom:.24rem; color:var(--text2); font-size:.64rem; font-weight:700; letter-spacing:.045em; text-transform:uppercase; }
.ll-field-value { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--text); font-family:'DM Mono',monospace; font-size:.9rem; }
.ll-field-value.money { color:var(--kc,var(--green)); font-weight:500; }

/* Confidence and status */
.ll-pill { display:inline-flex; align-items:center; padding:.08rem .34rem; border-radius:3px; font-family:'DM Mono',monospace; font-size:.59rem; line-height:1.4; }
.ll-pill.hi { background:var(--ok-bg); color:var(--ok); }
.ll-pill.mid { background:var(--warn-bg); color:var(--warn); }
.ll-pill.lo { background:var(--bad-bg); color:var(--bad); }
.ll-status { display:inline-flex; align-items:center; gap:.4rem; color:var(--text); font-size:.8rem; font-weight:600; }
.ll-status::before { content:""; width:.5rem; height:.5rem; border-radius:50%; flex:none; }
.ll-status.ok::before { background:var(--ok); }
.ll-status.pending::before { background:var(--warn); }
.ll-status.bad::before { background:var(--bad); }

/* Messages */
.ll-banner { margin:.45rem 0 1rem; padding:.75rem .9rem; border:1px solid var(--line); border-left:5px solid var(--blue); border-radius:2px 10px 2px 10px; background:var(--surface); color:var(--text2); font-size:.87rem; line-height:1.5; }
.ll-banner b { color:var(--text); }
.ll-banner.ok { border-left-color:var(--ok); }
.ll-banner.pending { border-left-color:var(--warn); }
.ll-banner.bad { border-left-color:var(--bad); }
.ll-banner.bad b { color:var(--bad); }
.ll-banner .mono { color:var(--text); font-family:'DM Mono',monospace; font-size:.82em; }

/* Tables */
.ll-table { width:100%; border-collapse:collapse; background:var(--surface); border:1px solid var(--line-strong); font-size:.84rem; }
.ll-table th { padding:.58rem .72rem; border-bottom:1px solid var(--line-strong); background:var(--surface2); color:var(--text2); font-size:.62rem; font-weight:700; letter-spacing:.045em; text-align:left; text-transform:uppercase; }
.ll-table td { padding:.56rem .72rem; border-bottom:1px solid var(--line); color:var(--text); }
.ll-table tbody tr:hover { background:var(--surface2); }
.ll-table tr:last-child td { border-bottom:0; }
.ll-table td.num { text-align:right; font-family:'DM Mono',monospace; }
.ll-table td.money { color:var(--green); font-weight:600; }

/* Review */
[data-testid="stExpander"] { overflow:hidden; border:1px solid var(--line-strong); border-left:5px solid var(--yellow); border-radius:2px 12px 2px 12px; background:var(--surface); box-shadow:none; }
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary * { color:var(--text) !important; font-weight:600; }
[class*="st-key-correction_"] { margin:.3rem 0; padding:.55rem .25rem .25rem; border-bottom:1px dashed var(--line); }
.ll-correction-label { color:var(--text2); font-size:.64rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; }
.ll-correction-value { padding-top:.25rem; color:var(--text); font-family:'DM Mono',monospace; font-size:.81rem; word-break:break-word; }
.ll-correction-help { padding-top:.15rem; color:var(--text3); font-size:.68rem; }

/* Ledger */
.ll-summary-strip { display:grid; grid-template-columns:repeat(5,1fr); margin:.3rem 0 1.6rem; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
.ll-summary-item { position:relative; min-width:0; padding:.85rem .8rem; border-right:1px solid var(--line); }
.ll-summary-item:last-child { border-right:0; }
.ll-summary-item::before { content:""; position:absolute; left:.8rem; top:-3px; width:2.2rem; height:5px; background:var(--metric,var(--accent)); }
.ll-summary-value { display:block; overflow:hidden; text-overflow:ellipsis; color:var(--text); font-family:'DM Mono',monospace; font-size:1.02rem; font-weight:500; white-space:nowrap; }
.ll-summary-label { display:block; margin-top:.15rem; color:var(--text2); font-size:.7rem; }
.ll-row-text { padding-top:.36rem; color:var(--text); font-size:.84rem; line-height:1.4; }
.ll-row-text .mono { color:var(--text2); font-family:'DM Mono',monospace; font-size:.76em; }
.ll-money-cell { padding-top:.36rem; color:var(--green); font-family:'DM Mono',monospace; font-size:.84rem; font-weight:500; }
.ll-col-head { color:var(--text2); font-size:.62rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; }
.ll-ledger-line { margin:.35rem 0; border-top:1px solid var(--line); }
[class*="st-key-detail_"] { margin:.5rem 0 1.1rem; padding:1rem; border:1px solid var(--line-strong); border-radius:0 14px 14px 14px; background:var(--surface); box-shadow:6px 7px 0 var(--panel-shadow); animation:enter .22s ease both; }
.ll-doc-img { display:block; width:auto; max-width:100%; max-height:430px; border:1px solid var(--line-strong); border-radius:2px; box-shadow:6px 7px 0 var(--panel-shadow); }

/* Buttons */
.stButton > button { min-height:2.5rem; border-radius:5px; font-size:.86rem; font-weight:700; transition:background .13s ease,border-color .13s ease,transform .13s ease,box-shadow .13s ease; }
.stButton > button *, .stButton > button p, .stButton > button span, .stButton > button div { color:inherit !important; }
.stButton > button:active { transform:translateY(1px); }
.stButton > button[kind="primary"] { border:2px solid var(--accent); background:var(--accent); color:var(--button-text); box-shadow:4px 4px 0 var(--button-shadow); }
.stButton > button[kind="primary"] * { color:var(--button-text) !important; }
.stButton > button[kind="primary"]:hover { border-color:var(--accent-hover); background:var(--accent-hover); color:var(--button-text); transform:translate(-1px,-1px); box-shadow:5px 5px 0 var(--button-shadow); }
.stButton > button[kind="secondary"] { border:1px solid var(--line-strong); background:var(--surface); color:var(--text); box-shadow:none; }
.stButton > button[kind="secondary"]:hover { border-color:var(--text2); background:var(--surface2); color:var(--text); transform:translateY(-1px); }
.stButton > button:disabled { opacity:.48; transform:none !important; box-shadow:none !important; }

/* Streamlit widgets */
[data-testid="stWidgetLabel"] p,[data-testid="stWidgetLabel"] label { color:var(--text2) !important; }
[data-testid="stFileUploaderDropzone"] { min-height:145px; border:1.5px dashed var(--line-strong); border-radius:8px 2px 8px 2px; background:var(--surface2); transition:border-color .15s ease,background .15s ease; }
[data-testid="stFileUploaderDropzone"]:hover { border-color:var(--accent); background:var(--accent-soft); }
[data-testid="stFileUploaderDropzone"] span,[data-testid="stFileUploaderDropzone"] small,[data-testid="stFileUploaderDropzone"] div { color:var(--text2) !important; }
[data-testid="stFileUploaderDropzone"] button { border:1px solid var(--line-strong) !important; background:var(--surface) !important; color:var(--text) !important; }
[data-testid="stFileUploaderDropzone"] button * { color:var(--text) !important; }
[data-testid="stTextInputRootElement"],.stTextInput input { border-color:var(--line) !important; background:var(--surface2) !important; color:var(--text) !important; }
.stTextInput input:focus { border-color:var(--blue) !important; box-shadow:0 0 0 1px var(--blue) !important; }
.stTextInput input::placeholder { color:var(--text3) !important; }
.stSpinner > div,[data-testid="stImageCaption"] { color:var(--text2) !important; }
[data-testid="stAlert"] { border-radius:4px; }

@media (max-width:900px) {
    .block-container { padding-top:5.4rem; }
    .st-key-topnav { padding-inline:.7rem; }
    .ll-brand-text { display:none; }
    .st-key-home_hero { min-height:auto; padding:3rem .25rem 2rem 2.9rem; }
    .st-key-home_hero::before { -webkit-mask-image:none; mask-image:none; }
    .ll-receipt-wrap { margin-top:1.5rem; }
    .ll-summary-strip { grid-template-columns:repeat(3,1fr); }
    .ll-summary-item:nth-child(3) { border-right:0; }
    .ll-summary-item:nth-child(n+4) { border-top:1px solid var(--line); }
}
@media (max-width:640px) {
    .block-container { padding-left:1rem; padding-right:1rem; }
    .st-key-topnav .stButton > button { font-size:.72rem !important; padding:.25rem .2rem !important; }
    .st-key-themebtn .stButton > button,.st-key-topnav .st-key-themebtn .stButton > button { min-width:3.9rem !important; padding:0 .3rem !important; font-size:.7rem !important; }
    .st-key-home_hero { padding-left:2.65rem; }
    .ll-home-copy h1 { font-size:2.85rem; }
    .ll-home-stats { grid-template-columns:1fr; }
    .ll-home-stat { border-right:0; border-bottom:1px solid var(--line); }
    .ll-home-stat:last-child { border-bottom:0; }
    .ll-field-grid { grid-template-columns:1fr; }
    .ll-field { border-right:0; }
    .ll-empty-preview,.st-key-preview_card { border-left:0; padding-left:0; }
    .ll-summary-strip { grid-template-columns:1fr 1fr; }
    .ll-summary-item { border-top:1px solid var(--line); }
    .ll-summary-item:nth-child(-n+2) { border-top:0; }
    .ll-summary-item:nth-child(2n) { border-right:0; }
}
@media (prefers-reduced-motion:reduce) {
    *,*::before,*::after { animation:none !important; transition:none !important; scroll-behavior:auto !important; }
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
    "auto_approved": ("ok", "auto approved"),
    "approved": ("ok", "approved"),
    "pending_review": ("pending", "pending review"),
    "blocked": ("bad", "blocked"),
    "rejected": ("bad", "rejected"),
}
PAGES = [("home", "Home"), ("upload", "Extract"),
         ("review", "Review"), ("ledger", "Ledger")]
CARD_HUES = ["var(--red)", "var(--orange)", "var(--amber)", "var(--green)",
             "var(--teal)", "var(--blue)", "var(--violet)"]


@st.cache_data(ttl=5, show_spinner=False)
def fetch(path: str):
    response = requests.get(f"{API}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


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
    cards = []
    for i, name in enumerate(SCALAR_FIELDS):
        node = extraction.get(name, {"value": None, "confidence": 0})
        cards.append(
            field_card(
                name.replace("_", " ").title(),
                node.get("value"), node.get("confidence"),
                name in MONEY_FIELDS,
                hue=CARD_HUES[i % len(CARD_HUES)],
            )
        )
    st.markdown(
        f'<div class="ll-field-grid">{"".join(cards)}</div>',
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


def page_title(title: str, sub: str):
    st.markdown(
        f'<div class="ll-page-head">'
        f'<div class="ll-page-title rise">{esc(title)}</div>'
        f'<div class="ll-page-sub rise-1">{esc(sub)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def summary_strip(metrics) -> str:
    items = []
    for label, value, hue in metrics:
        items.append(
            f'<div class="ll-summary-item" style="--metric:{hue};">'
            f'<span class="ll-summary-value">{esc(value)}</span>'
            f'<span class="ll-summary-label">{esc(label)}</span>'
            f'</div>'
        )
    return f'<div class="ll-summary-strip">{"".join(items)}</div>'


def goto(page: str):
    st.session_state.page = page
    st.rerun()


# --------------------------------------------------------------------------- #
# Fixed top navigation
# --------------------------------------------------------------------------- #
with st.container(key="topnav"):
    brand_col, nav_col, theme_col = st.columns([1.65, 4.2, 1.05], gap="small")
    with brand_col:
        st.markdown(
            '<div class="ll-wordmark"><span class="ll-mark">LL</span>'
            '<span class="ll-brand-text">OnRecord</span></div>',
            unsafe_allow_html=True,
        )
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
            if st.button(
                    "Light" if DARK else "Dark",
                    key="theme_toggle",
                    help="Use light mode" if DARK else "Use dark mode",
                    use_container_width=True,
                ):
                st.session_state.theme = "light" if DARK else "dark"
                st.rerun()


# --------------------------------------------------------------------------- #
# PAGE: Home
# --------------------------------------------------------------------------- #
def page_home():
    with st.container(key="home_hero"):
        copy_col, receipt_col = st.columns([1.25, 0.75], gap="large")
        with copy_col:
            st.markdown(
                """
<div class="ll-home-copy rise">
  <h1>Receipts in.<br><span>Records out.</span></h1>
  <h2>Upload a receipt or invoice, check the details, and save it to the ledger.</h2>
</div>
""",
                unsafe_allow_html=True,
            )
            if st.button("Extract document", type="primary", use_container_width=True):
                goto("upload")
        with receipt_col:
            st.markdown(
                """
<div class="ll-receipt-wrap" aria-hidden="true">
  <div class="ll-receipt-pin"></div>
  <div class="ll-home-receipt">
    <div class="ll-receipt-store">Corner Shop</div>
    <div class="ll-receipt-meta">12 July | Receipt 1842</div>
    <div class="ll-receipt-line"><span>Bread and milk</span><span>8.40</span></div>
    <div class="ll-receipt-line"><span>Kitchen items</span><span>11.75</span></div>
    <div class="ll-receipt-line"><span>Tax</span><span>1.61</span></div>
    <div class="ll-receipt-total"><span>Total</span><span>21.76</span></div>
    <div class="ll-receipt-note">checked</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

    try:
        docs = fetch("/documents")
    except requests.RequestException:
        docs = None

    if docs is None:
        total_uploads = approved = pending = "-"
    else:
        total_uploads = len(docs)
        approved = sum(
            1 for doc in docs
            if doc.get("status") in {"auto_approved", "approved"}
        )
        pending = sum(
            1 for doc in docs
            if doc.get("status") == "pending_review"
        )

    st.markdown(
        f"""
<div class="ll-home-stats rise-1">
  <div class="ll-home-stat" style="--stat-color:var(--blue);">
    <span class="value">{esc(total_uploads)}</span>
    <span class="label">Uploaded</span>
  </div>
  <div class="ll-home-stat" style="--stat-color:var(--green);">
    <span class="value">{esc(approved)}</span>
    <span class="label">Approved</span>
  </div>
  <div class="ll-home-stat" style="--stat-color:var(--amber);">
    <span class="value">{esc(pending)}</span>
    <span class="label">Needs review</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# PAGE: Upload
# --------------------------------------------------------------------------- #
def page_upload():
    page_title(
        "Extract document",
        "Choose a JPG or PNG. Review the result after it is read.",
    )

    with st.container(key="upload_workspace"):
        upload_col, preview_col = st.columns([1.05, 0.95], gap="large")

        with upload_col:
            st.markdown(
                """
<div class="ll-upload-copy">
  <h3>Choose a file</h3>
  <p>Use one clear receipt or invoice.</p>
  <div class="ll-upload-help">
    <span>JPG or PNG</span>
    <span>One document per image</span>
    <span>Fix fields when needed</span>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
            uploaded = st.file_uploader(
                "Drop a receipt or invoice",
                type=["jpg", "jpeg", "png"],
                label_visibility="collapsed",
            )
            extract_clicked = st.button(
                "Extract document",
                type="primary",
                use_container_width=True,
                disabled=uploaded is None,
            )
            if uploaded is None:
                st.caption("Choose a file to start.")

        with preview_col:
            if uploaded is None:
                st.markdown(
                    """
<div class="ll-empty-preview">
  <div class="ll-empty-icon"></div>
  <b>No file selected</b>
  <p>Your receipt will appear here.</p>
</div>
""",
                    unsafe_allow_html=True,
                )
            else:
                with st.container(key="preview_card"):
                    st.image(uploaded, use_container_width=True)
                    size_kb = len(uploaded.getvalue()) / 1024
                    st.markdown(
                        f'<div class="ll-file-meta"><span>{esc(uploaded.name)}</span>'
                        f'<span>{size_kb:,.0f} KB</span></div>',
                        unsafe_allow_html=True,
                    )

    if not extract_clicked or uploaded is None:
        return

    with st.spinner("Reading the document..."):
        try:
            resp = requests.post(
                f"{API}/ingest",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                timeout=120,
            )
        except requests.RequestException as e:
            st.error(f"API unreachable: {e}")
            return

    st.cache_data.clear()
    st.markdown('<div class="ll-rule">Extraction result</div>', unsafe_allow_html=True)

    if resp.status_code == 422:
        try:
            detail = resp.json().get("detail", {})
        except ValueError:
            detail = {}
        banner(
            "bad",
            f"<b>Blocked.</b> "
            f"{esc(detail.get('blocked_reason', 'The document was flagged.'))}",
        )
        return

    if resp.status_code != 200:
        banner("bad", f"Error {resp.status_code}: {esc(resp.text)}")
        return

    try:
        data = resp.json()
    except ValueError:
        banner("bad", "The API returned an unreadable response.")
        return

    if data["status"] == "auto_approved":
        banner(
            "ok",
            f"<b>Approved.</b> All fields passed the checks. "
            f"Doc <span class='mono'>{esc(data['doc_id'])}</span>"
            f" | <span class='mono'>${data['cost_usd']:.5f}</span>",
        )
    else:
        n = len(data["flagged_fields"])
        banner(
            "pending",
            f"<b>{n} field{'s' if n != 1 else ''} need review.</b> "
            f"The document is in the Review queue. "
            f"Doc <span class='mono'>{esc(data['doc_id'])}</span>"
            f" | <span class='mono'>${data['cost_usd']:.5f}</span>",
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
            "Review queue",
            "Check the document, fix any values, then approve or reject it.",
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
        banner("ok", "No documents need review.")
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
            f"{item['filename']}  |  {item['doc_id']}  |  "
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
            corrected_values = {}
            for idx, flagged in enumerate(item["flagged_fields"]):
                field_path = str(flagged["field_path"])
                original_value = str(flagged.get("value", ""))
                with st.container(key=f"correction_{item['doc_id']}_{idx}"):
                    label_col, input_col = st.columns([1, 1.45], gap="medium")
                    with label_col:
                        st.markdown(
                            f'<div class="ll-correction-label">{esc(field_path)}</div>'
                            f'<div class="ll-correction-value">{esc(original_value)}</div>'
                            f'<div class="ll-correction-help">Confidence '
                            f'{pill(float(flagged.get("confidence", 0)))}</div>',
                            unsafe_allow_html=True,
                        )
                    with input_col:
                        corrected_values[field_path] = st.text_input(
                            f"Corrected value for {field_path}",
                            value=original_value,
                            label_visibility="collapsed",
                            key=f"corrected_{item['doc_id']}_{idx}",
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
                try:
                    r = requests.post(
                        f"{API}/reject",
                        json={"doc_id": item["doc_id"], "reason": reject_reason},
                        timeout=30,
                    )
                except requests.RequestException as e:
                    st.error(f"Reject failed: {e}")
                else:
                    if r.status_code == 200:
                        st.toast("Rejected.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Reject failed: {r.text}")

            if approve_clicked:
                corrections = [
                    {
                        "field_path": field_path,
                        "corrected_value": corrected_value,
                    }
                    for field_path, corrected_value in corrected_values.items()
                    if corrected_value != str(
                        next(
                            flagged.get("value", "")
                            for flagged in item["flagged_fields"]
                            if str(flagged["field_path"]) == field_path
                        )
                    )
                ]
                try:
                    r = requests.post(
                        f"{API}/approve",
                        json={"doc_id": item["doc_id"], "corrections": corrections},
                        timeout=30,
                    )
                except requests.RequestException as e:
                    st.error(f"Approve failed: {e}")
                else:
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
        "Ledger",
        "See every processed document. Open a row to view the image and details.",
    )

    try:
        docs = fetch("/documents")
    except requests.RequestException as e:
        st.error(f"API unreachable: {e}")
        docs = []

    if not docs:
        banner("pending", "No documents have been uploaded yet.")
        return

    df = pd.DataFrame(docs)
    n_auto = int((df["status"] == "auto_approved").sum())
    n_appr = int((df["status"] == "approved").sum())
    n_pend = int((df["status"] == "pending_review").sum())
    n_rej = int(df["status"].isin(["rejected", "blocked"]).sum())
    spend = df["cost_usd"].sum()

    st.markdown(
        summary_strip(
            [
                ("Auto approved", n_auto, "var(--teal)"),
                ("Approved", n_appr, "var(--green)"),
                ("Needs review", n_pend, "var(--amber)"),
                ("Rejected or blocked", n_rej, "var(--red)"),
                ("Processing cost", f"${spend:.4f}", "var(--violet)"),
            ]
        ),
        unsafe_allow_html=True,
    )

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
            ts = str(d.get("created_at", ""))[:16].replace("T", " at ")
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

        st.markdown('<div class="ll-ledger-line"></div>', unsafe_allow_html=True)

        if st.session_state.open_doc == d["doc_id"]:
            with st.container(key=f"detail_{d['doc_id']}"):
                di, dm = st.columns([1.3, 1], gap="large")
                with di:
                    st.markdown(
                        f'<img class="ll-doc-img" src="{API}/image/{d["doc_id"]}"/>',
                        unsafe_allow_html=True,
                    )
                    st.caption("The document id and UTC time are shown in the lower right.")
                with dm:
                    total = d.get("total")
                    detail_fields = (
                        field_card("Vendor", d.get("vendor") or "-", hue="var(--blue)")
                        + field_card(
                            "Total",
                            f"{total:,.2f}" if isinstance(total, (int, float)) else "-",
                            None, True, hue="var(--green)",
                        )
                        + field_card("Currency", d.get("currency") or "-", hue="var(--teal)")
                        + field_card(
                            "Cost", f"${d.get('cost_usd', 0):.5f}",
                            None, True, hue="var(--violet)",
                        )
                    )
                    st.markdown(
                        f'<div class="ll-field-grid ll-field-grid-single">{detail_fields}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(status_chip(d["status"]), unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
{"home": page_home, "upload": page_upload,
 "review": page_review, "ledger": page_ledger}[st.session_state.page]()

'''