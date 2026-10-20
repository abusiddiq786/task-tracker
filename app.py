"""
Team Task Tracker for Fusstees & KMR Garments
Works on phone + desktop. Data is stored in your Google Sheet.

You do NOT need to edit this file. Settings (staff, areas) are managed
inside the app (Team tab) or directly in the Google Sheet.
"""

import calendar
import hashlib
import hmac
import html
import time
import uuid
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------
# Basic settings (safe to change the text in quotes if you want)
# ---------------------------------------------------------------
APP_NAME = "Task Tracker"
BUSINESS_NAME = "Fusstees & KMR Garments"
ADMIN_DEFAULT_NAME = "Abubakkar"
ADMIN_DEFAULT_PIN = "1234"  # change this after first login (Team tab)

DEFAULT_AREAS = [
    "Meesho",
    "Flipkart",
    "KMR Wholesale",
    "Offline / Rack",
    "Suppliers & Payments",
    "Production / Stock",
    "Tools & Automation",
]

# ---------------------------------------------------------------
# Internal settings (do not change)
# ---------------------------------------------------------------
IST = ZoneInfo("Asia/Kolkata")
TASK_COLS = [
    "id", "title", "area", "repeat", "priority", "due_date", "status",
    "assigned_to", "waiting_on", "waiting_since", "notes",
    "created_by", "created_at", "done_by", "done_at",
]
USER_COLS = ["name", "pin", "role", "active"]
AREA_COLS = ["area"]
HEADERS = {"Tasks": TASK_COLS, "Users": USER_COLS, "Areas": AREA_COLS}

REPEATS = ["None", "Daily", "Weekly", "Monthly"]
PRIORITIES = ["High", "Medium", "Low"]
EVERYONE = "Everyone"
PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}

st.set_page_config(page_title=APP_NAME, page_icon=":material/checklist:", layout="centered")


# ---------------------------------------------------------------
# Look and feel (colours, fonts, card styles)
# ---------------------------------------------------------------
# Fixed colour per business area, in order. New areas get the next colour.
AREA_COLORS = ["#5B7DB1", "#8C6BB1", "#B5657F", "#4E918C", "#C0794A", "#6A70B8", "#7C9550", "#A08350"]
STATUS_LABEL = {"Doing": "In progress", "Waiting": "Waiting", "Done": "Done"}
MONOGRAM = "F&amp;K"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Manrope:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..24,400,0,0&display=block');

:root {
  --ink: #1C1C1F; --ink-2: #3A3A40; --muted: #7B776F; --faint: #A9A49A;
  --bg: #F6F3EE; --card: #FFFFFF; --line: #E8E3DA; --line-2: #DDD6CA; --tint: #FAF8F4;
  --gold: #B08D57; --gold-soft: #F4EDE1;
  --high: #B4543D; --high-soft: #F8EBE7;
  --medium: #A9822F; --medium-soft: #F7F0E1;
  --low: #5D8068; --low-soft: #EAF1EC;
  --blue: #4F6F96; --blue-soft: #EAF0F6;
  --radius: 16px;
  --shadow: 0 1px 2px rgba(28,28,31,.04), 0 8px 24px -12px rgba(28,28,31,.10);
}

html, body, .stApp, [class*="css"], button, input, textarea, select, p, label {
  font-family: 'Manrope', system-ui, sans-serif !important; letter-spacing: -.005em;
}
.stApp { background: var(--bg); color: var(--ink); }
h1, h2, h3, .tt-serif { font-family: 'Fraunces', Georgia, serif !important; font-weight: 500 !important; letter-spacing: -.01em; }
.ms {
  font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1;
  font-size: 1.05em; display: inline-block; vertical-align: -0.18em; -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga';
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stHeaderActionElements"], footer { display: none !important; }
.block-container { padding: 1.4rem 1rem 4rem !important; max-width: 760px; }
h3 { font-size: 1.2rem !important; margin: 1.8rem 0 .6rem !important; color: var(--ink); }
.tt-eyebrow { font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }

/* ---------- Buttons ---------- */
.stButton, [data-testid="stFormSubmitButton"], [data-testid="stPopover"],
[data-testid="stElementContainer"]:has(.stButton),
[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]),
[data-testid="stFormSubmitButton"] > *, .stButton > *,
[data-testid="stLayoutWrapper"]:has(> [data-testid="stPopover"]) { width: 100% !important; }
.st-key-topbar .stButton, .st-key-topbar .stButton > *, .st-key-topbar [data-testid="stElementContainer"] { width: auto !important; }
.stButton button, [data-testid="stFormSubmitButton"] button, [data-testid="stPopover"] button {
  width: 100%; min-height: 42px; border-radius: 12px; font-weight: 600; font-size: .9rem; letter-spacing: 0;
  border: 1px solid var(--line-2); background: var(--card); color: var(--ink);
  box-shadow: 0 1px 1px rgba(28,28,31,.03); transition: background .15s ease, border-color .15s ease, transform .06s ease;
}
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover, [data-testid="stPopover"] button:hover {
  border-color: var(--ink); color: var(--ink); background: var(--tint);
}
.stButton button:active, [data-testid="stFormSubmitButton"] button:active { transform: scale(.98); }
.stButton button:focus-visible, [data-testid="stPopover"] button:focus-visible { box-shadow: 0 0 0 3px rgba(176,141,87,.35) !important; }
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--ink) !important; border-color: var(--ink) !important; color: #fff !important;
  box-shadow: 0 6px 16px -8px rgba(28,28,31,.55) !important;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background: #000 !important; color: #fff !important;
}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p { color: #fff !important; }
button [data-testid="stIconMaterial"] { font-size: 1.15rem; }

/* ---------- Inputs ---------- */
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"], [data-testid="stDateInputField"],
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"] {
  border: 1px solid var(--line-2) !important; border-radius: 12px !important; background: var(--card) !important;
  transition: border-color .15s ease, box-shadow .15s ease;
}
[data-testid="stTextInputRootElement"], [data-testid="stDateInputField"], [data-testid="stSelectbox"] [role="group"] { min-height: 46px; }
[data-testid="stTextInputRootElement"]:focus-within, [data-testid="stTextAreaRootElement"]:focus-within,
[data-testid="stDateInputField"]:focus-within, [data-testid="stSelectbox"] [role="group"]:focus-within,
[data-testid="stMultiSelect"] [role="group"]:focus-within {
  border-color: var(--ink) !important; box-shadow: 0 0 0 3px rgba(28,28,31,.06);
}
[data-testid="stWidgetLabel"] p { font-size: .74rem !important; font-weight: 700 !important; letter-spacing: .08em; text-transform: uppercase; color: var(--muted) !important; }
[data-testid="stForm"] {
  background: var(--card); border: 1px solid var(--line) !important; border-radius: 20px; padding: 1.4rem 1.2rem;
  box-shadow: var(--shadow);
}

/* Radios as quiet segmented chips */
[data-testid="stRadioGroup"] > div { gap: 6px !important; flex-wrap: wrap; }
[data-testid="stRadioOption"] {
  background: var(--card); border: 1px solid var(--line-2); border-radius: 999px; padding: 8px 16px 8px 12px !important;
  margin: 0 !important; min-height: 40px; transition: all .15s ease;
}
[data-testid="stRadioOption"]:has(input:checked) { border-color: var(--ink); background: var(--ink); }
[data-testid="stRadioOption"]:has(input:checked) p { color: #fff !important; }
[data-testid="stRadioOption"] p { font-weight: 600; font-size: .9rem; }

/* ---------- Tabs: segmented control ---------- */
.stTabs [role="tablist"] {
  gap: 2px; overflow-x: auto; scrollbar-width: none; padding: 4px; margin-bottom: 1rem;
  background: #EEEAE3; border: 0 !important; border-radius: 14px; box-shadow: none !important;
}
.stTabs [role="tablist"]::-webkit-scrollbar { display: none; }
.stTabs [role="tab"] {
  height: 40px; padding: 0 14px; border-radius: 10px; white-space: nowrap; flex: 1 0 auto; justify-content: center;
  color: var(--muted); background: transparent; border: 0 !important; outline: none; box-shadow: none !important;
  transition: background .15s ease, color .15s ease;
}
.stTabs [role="tab"] p { font-size: .88rem; font-weight: 600; }
.stTabs [role="tab"]:hover { color: var(--ink); }
.stTabs [role="tab"][aria-selected="true"] {
  background: var(--card) !important; color: var(--ink) !important;
  box-shadow: 0 1px 2px rgba(28,28,31,.06), 0 2px 8px -2px rgba(28,28,31,.08) !important;
}
.stTabs [role="tab"]:focus-visible { box-shadow: 0 0 0 2px var(--gold) !important; }
.stTabs [role="tab"] > div ~ div, [data-testid^="stTabsScroll"] { display: none !important; }

/* ---------- Header ---------- */
.tt-brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.tt-mono {
  width: 44px; height: 44px; flex: none; border-radius: 50%; display: grid; place-items: center;
  background: var(--ink); color: #F3E7D3; font-family: 'Fraunces', serif; font-size: .95rem; font-weight: 500;
  letter-spacing: .02em; box-shadow: inset 0 0 0 2px var(--ink), inset 0 0 0 3px rgba(243,231,211,.35);
}
.tt-brand-name { font-family: 'Fraunces', serif; font-size: 1.35rem; font-weight: 500; line-height: 1.15; color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
@media (max-width: 480px) { .tt-brand-name { font-size: 1.15rem; } .tt-mono { width: 40px; height: 40px; font-size: .85rem; } }
.tt-brand-sub { color: var(--muted); font-size: .8rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }
.st-key-topbar { padding-bottom: 14px; margin-bottom: 4px; border-bottom: 1px solid var(--line); }
.st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center; gap: 8px; }
.st-key-topbar [data-testid="stColumn"] { min-width: 0 !important; }
.st-key-topbar [data-testid="stColumn"]:not(:first-child) { flex: 0 0 auto !important; width: auto !important; }
.st-key-topbar .stButton button { min-height: 40px; padding: 0 14px; font-size: .85rem; border-radius: 999px; }

/* ---------- Login ---------- */
.tt-hero { text-align: center; padding: 2.4rem 0 1.4rem; }
.tt-hero .tt-mono { margin: 0 auto 18px; width: 68px; height: 68px; font-size: 1.35rem; }
.tt-hero h1 { font-size: 2.2rem !important; margin: 6px 0 0 !important; padding: 0 !important; }
.tt-hero p { color: var(--muted); margin: 6px 0 0; font-size: .95rem; }

/* ---------- Task cards ---------- */
[class*="st-key-card_"] {
  background: var(--card); border: 1px solid var(--line) !important; border-radius: var(--radius) !important;
  padding: 16px 16px 14px 20px !important; box-shadow: var(--shadow); gap: .75rem !important; position: relative; overflow: hidden;
}
[class*="st-key-card_"]::before {
  content: ""; position: absolute; left: 0; top: 14px; bottom: 14px; width: 3px; border-radius: 0 3px 3px 0; background: var(--medium);
}
[class*="st-key-card_high"]::before { background: var(--high); }
[class*="st-key-card_low"]::before { background: var(--low); }
[class*="_done_"] { background: var(--tint); box-shadow: none; }
[class*="_done_"]::before { background: var(--line-2) !important; }
.tt-title { font-size: 1.04rem; font-weight: 700; line-height: 1.35; color: var(--ink); margin-bottom: 10px; }
.tt-title.done { text-decoration: line-through; text-decoration-color: var(--faint); color: var(--muted); }
.tt-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.tt-tag {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
  font-size: .74rem; font-weight: 700; letter-spacing: .01em; color: var(--ink-2);
  background: var(--card); border: 1px solid var(--line); white-space: nowrap;
}
.tt-tag .ms { font-size: .95rem; vertical-align: 0; }
.tt-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c, var(--muted)); }
.tt-tag.prio-High { background: var(--high-soft); border-color: transparent; color: var(--high); }
.tt-tag.prio-Medium { background: var(--medium-soft); border-color: transparent; color: var(--medium); }
.tt-tag.prio-Low { background: var(--low-soft); border-color: transparent; color: var(--low); }
.tt-tag.prio-High .tt-dot { background: var(--high); }
.tt-tag.prio-Medium .tt-dot { background: var(--medium); }
.tt-tag.prio-Low .tt-dot { background: var(--low); }
.tt-tag.st-Doing { background: var(--blue-soft); border-color: transparent; color: var(--blue); }
.tt-tag.st-Done { background: var(--low-soft); border-color: transparent; color: var(--low); }
.tt-meta { display: flex; flex-wrap: wrap; gap: 4px 16px; color: var(--muted); font-size: .84rem; font-weight: 500; }
.tt-meta .ms { color: var(--faint); margin-right: 3px; }
.tt-meta .late { color: var(--high); font-weight: 700; }
.tt-meta .late .ms, .tt-meta .today .ms { color: inherit; }
.tt-meta .today { color: var(--ink); font-weight: 700; }
.tt-alert { margin-top: 10px; padding: 8px 12px; border-radius: 10px; font-size: .84rem; font-weight: 600; display: flex; gap: 8px; align-items: center; }
.tt-alert.red { background: var(--high-soft); color: var(--high); }
.tt-alert.amber { background: var(--medium-soft); color: #86651F; }
.tt-note { margin-top: 10px; padding: 8px 12px; border-radius: 10px; background: var(--tint); border: 1px solid var(--line); color: var(--ink-2); font-size: .85rem; display: flex; gap: 8px; }
.tt-note .ms { color: var(--faint); }
.tt-done-by { margin-top: 10px; color: var(--low); font-size: .82rem; font-weight: 600; display: flex; gap: 6px; align-items: center; }
/* Card buttons: compact, all on one row */
[class*="st-key-card_"] [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important; flex-direction: row !important; gap: 6px !important;
  padding-top: 12px; margin-top: 2px; border-top: 1px solid var(--line);
}
[class*="st-key-card_"] [data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
[class*="st-key-card_"] .stButton button, [class*="st-key-card_"] [data-testid="stPopover"] button {
  min-height: 36px; height: 36px; padding: 0 8px; border-radius: 10px; font-size: .8rem; gap: 4px;
}
[class*="st-key-card_"] button p { font-size: .8rem !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
[class*="st-key-card_"] button [data-testid="stIconMaterial"] { font-size: 1rem; }
[data-testid="stPopoverButton"] > div > div[aria-hidden="true"] { display: none; }
/* Narrow phones: text-only card buttons so all four fit on one row */
@media (max-width: 480px) {
  [class*="st-key-card_"] button [data-testid="stIconMaterial"],
  [class*="st-key-card_"] button span:has(> [data-testid="stIconMaterial"]),
  [class*="st-key-card_"] button p span[role="img"] { display: none !important; }
  [class*="st-key-card_"] .stButton button, [class*="st-key-card_"] [data-testid="stPopover"] button { padding: 0 4px; }
}

/* ---------- Summary + empty ---------- */
.tt-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin: 4px 0 14px; }
.tt-summary .count { font-family: 'Fraunces', serif; font-size: 1.6rem; font-weight: 500; color: var(--ink); line-height: 1; }
.tt-summary .lbl { color: var(--muted); font-size: .88rem; font-weight: 600; }
.tt-summary .late { color: var(--high); font-size: .85rem; font-weight: 700; background: var(--high-soft); padding: 3px 10px; border-radius: 999px; }
.tt-empty { text-align: center; padding: 2.2rem 1rem; background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); color: var(--muted); font-weight: 500; font-size: .92rem; }
.tt-empty .ms { display: block; margin: 0 auto 8px; font-size: 1.8rem; color: var(--gold); }

/* ---------- Dashboard ---------- */
.tt-kpis { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 4px 0 6px; }
@media (min-width: 640px) { .tt-kpis { grid-template-columns: repeat(4, 1fr); } }
.tt-kpi { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 16px; box-shadow: var(--shadow); }
.tt-kpi-label { color: var(--muted); font-size: .68rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; display: flex; align-items: center; gap: 6px; }
.tt-kpi-label .ms { font-size: 1rem; color: var(--faint); }
.tt-kpi-num { font-family: 'Fraunces', serif; font-size: 2.3rem; font-weight: 500; line-height: 1; margin-top: 12px; color: var(--ink); }
.tt-kpi.alert .tt-kpi-num, .tt-kpi.alert .tt-kpi-label .ms { color: var(--high); }
.tt-panel { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 8px 16px; box-shadow: var(--shadow); }
.tt-bar-row { display: grid; grid-template-columns: minmax(100px, 40%) 1fr 26px; align-items: center; gap: 12px; padding: 9px 0; }
.tt-bar-row + .tt-bar-row { border-top: 1px solid var(--line); }
.tt-bar-label { font-size: .86rem; font-weight: 600; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tt-bar-track { height: 8px; border-radius: 4px; background: #F1EDE6; }
.tt-bar { height: 100%; border-radius: 4px; background: var(--ink); min-width: 4px; }
.tt-bar-row:hover .tt-bar { background: var(--gold); }
.tt-bar-val { text-align: right; font-weight: 700; font-size: .88rem; color: var(--ink); }
.tt-table, .tt-table th, .tt-table td, .tt-table tr { border: 0 !important; background: transparent !important; }
.tt-table { width: 100%; border-collapse: collapse; font-size: .9rem; margin: 0 !important; }
.tt-table th { text-align: right; color: var(--muted); font-size: .66rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; padding: 10px 6px 8px; }
.tt-table th:first-child, .tt-table td:first-child { text-align: left; }
.tt-table td { text-align: right; padding: 11px 6px; border-top: 1px solid var(--line) !important; font-weight: 700; color: var(--ink); }
.tt-table td:first-child { font-weight: 600; }
.tt-table td.late { color: var(--high); }
.tt-table td.zero { color: var(--faint); font-weight: 500; }
.tt-list-item { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; border-top: 1px solid var(--line); }
.tt-list-item:first-child { border-top: 0; }
.tt-list-main { font-weight: 600; font-size: .9rem; color: var(--ink); }
.tt-list-sub { color: var(--muted); font-size: .78rem; font-weight: 500; margin-top: 2px; }
.tt-list-side { white-space: nowrap; font-weight: 700; font-size: .78rem; padding: 3px 10px; border-radius: 999px; }
.tt-list-side.late { color: var(--high); background: var(--high-soft); }
.tt-list-side.ok { color: var(--low); background: var(--low-soft); }

[data-testid="stAlert"] { border-radius: 12px; }
[class*="st-key-remember_box_"] { display: none !important; }
[data-testid="stPopoverBody"] { border-radius: 16px !important; border: 1px solid var(--line) !important; box-shadow: 0 20px 40px -16px rgba(28,28,31,.25) !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def esc(text) -> str:
    return html.escape(str(text or ""))


def ic(name: str) -> str:
    """A clean line icon (Google Material Symbols)."""
    return f'<span class="ms">{name}</span>'


def area_color(area: str) -> str:
    areas = DEFAULT_AREAS
    try:
        areas = area_list()
    except Exception:
        pass
    i = areas.index(area) if area in areas else sum(map(ord, area))
    return AREA_COLORS[i % len(AREA_COLORS)]


def show_html(*parts: str):
    """Renders our own HTML. Joined without newlines so Markdown leaves it alone."""
    st.markdown("".join(parts), unsafe_allow_html=True)


def empty_state(icon: str, msg: str):
    show_html(f'<div class="tt-empty">{ic(icon)}{esc(msg)}</div>')


# ---------------------------------------------------------------
# Date helpers (India time)
# ---------------------------------------------------------------
def today() -> date:
    return datetime.now(IST).date()


def now_str() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M")


def parse_date(value):
    """Reads dates written by the app or typed by hand in the sheet."""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def nice_date(d) -> str:
    if not d or d == date.max:
        return "No date"
    if d == today():
        return "Today"
    if d == today() + timedelta(days=1):
        return "Tomorrow"
    return d.strftime("%d %b")


def add_one_month(d: date) -> date:
    year = d.year + (d.month // 12)
    month = d.month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_due(d: date, repeat: str) -> date:
    if repeat == "Daily":
        return d + timedelta(days=1)
    if repeat == "Weekly":
        return d + timedelta(days=7)
    if repeat == "Monthly":
        return add_one_month(d)
    return d


# ---------------------------------------------------------------
# Google Sheet connection
# ---------------------------------------------------------------
@st.cache_resource
def get_book():
    creds = dict(st.secrets["gcp_service_account"])
    client = gspread.service_account_from_dict(creds)
    return client.open_by_url(st.secrets["sheet_url"])


@st.cache_resource
def ws(name: str):
    """Returns a sheet tab. Creates it with headers if missing."""
    book = get_book()
    headers = HEADERS[name]
    try:
        sheet = book.worksheet(name)
    except gspread.WorksheetNotFound:
        sheet = book.add_worksheet(title=name, rows=2000, cols=len(headers))
    if not sheet.row_values(1):
        sheet.update(range_name="A1", values=[headers], value_input_option="RAW")
    return sheet


@st.cache_data(ttl=20, show_spinner=False)
def load(name: str) -> pd.DataFrame:
    rows = ws(name).get_all_records(numericise_ignore=["all"])
    df = pd.DataFrame(rows)
    for col in HEADERS[name]:
        if col not in df.columns:
            df[col] = ""
    return df[HEADERS[name]].fillna("").astype(str)


def refresh():
    load.clear()


def col_letter(n: int) -> str:
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def find_row(sheet, value: str):
    cell = sheet.find(str(value), in_column=1)
    return cell.row if cell else None


# ---------------------------------------------------------------
# Writing data
# ---------------------------------------------------------------
def add_task(**fields):
    row = {c: "" for c in TASK_COLS}
    row.update({k: str(v) for k, v in fields.items()})
    row["id"] = uuid.uuid4().hex[:10]
    row["status"] = row["status"] or "To Do"
    row["created_at"] = row["created_at"] or now_str()
    ws("Tasks").append_row([row[c] for c in TASK_COLS], value_input_option="RAW")
    refresh()


def update_fields(sheet_name: str, key: str, fields: dict) -> bool:
    sheet = ws(sheet_name)
    row = find_row(sheet, key)
    if not row:
        st.warning("Could not find that item. Someone may have deleted it. Tap Refresh.")
        return False
    cols = HEADERS[sheet_name]
    data = [
        {"range": f"{col_letter(cols.index(k) + 1)}{row}", "values": [[str(v)]]}
        for k, v in fields.items()
    ]
    sheet.batch_update(data, value_input_option="RAW")
    refresh()
    return True


def delete_task(task_id: str):
    sheet = ws("Tasks")
    row = find_row(sheet, task_id)
    if row:
        sheet.delete_rows(row)
    refresh()


def complete_task(task: dict, user: str):
    """Marks a task Done. Repeating tasks create their next copy automatically."""
    sheet = ws("Tasks")
    row = find_row(sheet, task["id"])
    if not row:
        st.warning("This task no longer exists. Tap Refresh.")
        return
    status_col = TASK_COLS.index("status") + 1
    if sheet.cell(row, status_col).value == "Done":
        refresh()
        return  # someone already completed it

    update_fields("Tasks", task["id"], {"status": "Done", "done_by": user, "done_at": now_str()})

    repeat = task.get("repeat", "None")
    if repeat in ("Daily", "Weekly", "Monthly"):
        base = parse_date(task["due_date"]) or today()
        nxt = next_due(base, repeat)
        while nxt < today():
            nxt = next_due(nxt, repeat)
        add_task(
            title=task["title"], area=task["area"], repeat=repeat,
            priority=task["priority"], due_date=nxt.isoformat(),
            assigned_to=task["assigned_to"], notes=task["notes"],
            created_by="Auto (repeat)",
        )


# ---------------------------------------------------------------
# First-time setup
# ---------------------------------------------------------------
@st.cache_resource
def ensure_setup():
    users = ws("Users")
    if len(users.get_all_values()) <= 1:
        users.append_row([ADMIN_DEFAULT_NAME, ADMIN_DEFAULT_PIN, "admin", "yes"],
                         value_input_option="RAW")

    areas = ws("Areas")
    if len(areas.get_all_values()) <= 1:
        areas.append_rows([[a] for a in DEFAULT_AREAS], value_input_option="RAW")

    tasks = ws("Tasks")
    if len(tasks.get_all_values()) <= 1:
        t = today()
        saturday = t + timedelta(days=(5 - t.weekday()) % 7)
        fifth = date(t.year, t.month, 5)
        if fifth < t:
            fifth = add_one_month(fifth)
        samples = [
            ("Process Meesho labels for all accounts", "Meesho", "Daily", "High", t),
            ("Check Flipkart orders and returns", "Flipkart", "Daily", "High", t),
            ("Pay job-work suppliers", "Suppliers & Payments", "Weekly", "Medium", saturday),
            ("Visit rack shops and collect payments", "Offline / Rack", "Weekly", "Medium", saturday),
            ("Monthly P&L check for Meesho and Flipkart", "Tools & Automation", "Monthly", "High", fifth),
        ]
        for title, area, repeat, prio, due in samples:
            add_task(title=title, area=area, repeat=repeat, priority=prio,
                     due_date=due.isoformat(), assigned_to=ADMIN_DEFAULT_NAME,
                     created_by="Setup")
    refresh()
    return True


# ---------------------------------------------------------------
# Data views
# ---------------------------------------------------------------
def prepared_tasks() -> pd.DataFrame:
    df = load("Tasks").copy()
    df["_due"] = df["due_date"].apply(lambda s: parse_date(s) or date.max)
    df["_rank"] = df["priority"].map(PRIORITY_RANK).fillna(1)
    return df.sort_values(["_due", "_rank"], kind="stable")


def active_people() -> list:
    users = load("Users")
    users = users[users["active"].str.lower() != "no"]
    return users["name"].tolist()


def area_list() -> list:
    areas = load("Areas")["area"].tolist()
    return [a for a in areas if a.strip()] or DEFAULT_AREAS


def for_person(df: pd.DataFrame, user: str) -> pd.DataFrame:
    return df[df["assigned_to"].isin([user, EVERYONE])]


def safe_index(options: list, value: str, default: int = 0) -> int:
    return options.index(value) if value in options else default


# ---------------------------------------------------------------
# Task card
# ---------------------------------------------------------------
def render_task(t: dict, prefix: str, user: str, is_admin: bool):
    tid = t["id"]
    key = f"{prefix}_{tid}"
    due = parse_date(t["due_date"])
    status = t["status"]
    prio = t["priority"] if t["priority"] in PRIORITY_RANK else "Medium"
    done = status == "Done"
    late = not done and due and due < today()

    with st.container(key=f"card_{prio.lower()}_{'done' if done else 'open'}_{key}"):
        tags = [f'<span class="tt-tag prio-{prio}"><span class="tt-dot"></span>{prio}</span>']
        if t["area"]:
            tags.append(f'<span class="tt-tag area" style="--c:{area_color(t["area"])}">'
                        f'<span class="tt-dot"></span>{esc(t["area"])}</span>')
        if t["repeat"] in ("Daily", "Weekly", "Monthly"):
            tags.append(f'<span class="tt-tag">{ic("autorenew")}{t["repeat"]}</span>')
        if status in ("Doing", "Done"):
            tags.append(f'<span class="tt-tag st-{status}">{STATUS_LABEL[status]}</span>')

        due_cls = "late" if late else ("today" if due == today() and not done else "")
        parts = [
            f'<div class="tt-title{" done" if done else ""}">{esc(t["title"])}</div>',
            f'<div class="tt-tags">{"".join(tags)}</div>',
            f'<div class="tt-meta"><span>{ic("person")}{esc(t["assigned_to"] or "Unassigned")}</span>'
            f'<span class="{due_cls}">{ic("event")}{nice_date(due)}</span></div>',
        ]
        if late:
            days = (today() - due).days
            parts.append(f'<div class="tt-alert red">{ic("error")}Overdue by {days} day{"s" if days > 1 else ""}</div>')
        if status == "Waiting":
            since = parse_date(t["waiting_since"])
            days = (today() - since).days if since else 0
            parts.append(f'<div class="tt-alert amber">{ic("hourglass_top")}Waiting on {esc(t["waiting_on"] or "someone")} '
                         f'for {days} day{"s" if days != 1 else ""}</div>')
        if t["notes"]:
            parts.append(f'<div class="tt-note">{ic("notes")}<span>{esc(t["notes"])}</span></div>')
        if done:
            parts.append(f'<div class="tt-done-by">{ic("check_circle")}Done by {esc(t["done_by"])} at {esc(t["done_at"])}</div>')
        show_html(*parts)
        if done:
            return

        # Only make columns for the buttons this card actually shows
        actions = ["done"]
        if status in ("To Do", "Waiting"):
            actions.append("start")
        if status != "Waiting":
            actions.append("wait")
        if is_admin:
            actions.append("edit")
        cols = dict(zip(actions, st.columns(len(actions))))

        if cols["done"].button("Done", icon=":material/check:", key=f"{key}_done", type="primary"):
            complete_task(t, user)
            st.session_state.flash = f"Done: {t['title']}"
            st.rerun()

        if status == "To Do":
            if cols["start"].button("Start", icon=":material/play_arrow:", key=f"{key}_start"):
                update_fields("Tasks", tid, {"status": "Doing"})
                st.rerun()
        elif status == "Waiting":
            if cols["start"].button("Resume", icon=":material/play_arrow:", key=f"{key}_resume"):
                update_fields("Tasks", tid, {"status": "Doing", "waiting_on": "", "waiting_since": ""})
                st.rerun()

        if "wait" in cols:
            with cols["wait"].popover(":material/schedule: Waiting"):
                who = st.text_input("Waiting on whom or what?", key=f"{key}_who",
                                    placeholder="e.g. Ravi supplier, fabric delivery")
                if st.button("Save", key=f"{key}_wait_save"):
                    update_fields("Tasks", tid, {"status": "Waiting", "waiting_on": who,
                                                 "waiting_since": today().isoformat()})
                    st.rerun()

        if "edit" in cols:
            with cols["edit"].popover(":material/edit: Edit"):
                edit_form(t, key)


def edit_form(t: dict, key: str):
    areas = area_list()
    people = [EVERYONE] + active_people()
    with st.form(f"{key}_edit"):
        title = st.text_input("Task", t["title"], key=f"{key}_e_title")
        area = st.selectbox("Area", areas, index=safe_index(areas, t["area"]), key=f"{key}_e_area")
        assigned = st.selectbox("Assigned to", people, index=safe_index(people, t["assigned_to"]),
                                key=f"{key}_e_who")
        priority = st.selectbox("Priority", PRIORITIES, index=safe_index(PRIORITIES, t["priority"], 1),
                                key=f"{key}_e_prio")
        repeat = st.selectbox("Repeat", REPEATS, index=safe_index(REPEATS, t["repeat"]), key=f"{key}_e_rep")
        due = st.date_input("Due date", parse_date(t["due_date"]) or today(), format="DD/MM/YYYY",
                            key=f"{key}_e_due")
        notes = st.text_area("Notes", t["notes"], key=f"{key}_e_notes")
        if st.form_submit_button("Save changes", type="primary"):
            update_fields("Tasks", t["id"], {
                "title": title.strip() or t["title"], "area": area, "assigned_to": assigned,
                "priority": priority, "repeat": repeat, "due_date": due.isoformat(), "notes": notes,
            })
            st.rerun()
    sure = st.checkbox("Yes, delete this task", key=f"{key}_sure")
    if st.button("Delete task", icon=":material/delete:", key=f"{key}_delete", disabled=not sure):
        delete_task(t["id"])
        st.rerun()


def render_list(df: pd.DataFrame, prefix: str, user: str, is_admin: bool, empty_msg: str, limit: int = 100):
    if df.empty:
        empty_state("task_alt", empty_msg)
        return
    if len(df) > limit:
        st.caption(f"Showing first {limit} of {len(df)} tasks. Use the filters to narrow down.")
    for _, row in df.head(limit).iterrows():
        render_task(row.to_dict(), prefix, user, is_admin)


# ---------------------------------------------------------------
# Stay logged in (signed token kept in the phone's browser storage, so
# switching apps doesn't ask for the PIN again). The PIN check is unchanged.
# ---------------------------------------------------------------
REMEMBER_DAYS = 30
_remember = components.declare_component(
    "remember", path=str(Path(__file__).parent / "remember_component"))


def remember(action: str, token: str = ""):
    """action: 'read' returns the saved token ('' if none, None until the browser answers),
    'save' stores a token, 'clear' removes it."""
    with st.container(key=f"remember_box_{action}"):
        return _remember(action=action, token=token, key=f"remember_{action}", default=None)


def _signature(name: str, pin: str, expires: int) -> str:
    key = str(st.secrets["gcp_service_account"]["private_key"]).encode()
    return hmac.new(key, f"{name}|{pin}|{expires}".encode(), hashlib.sha256).hexdigest()[:32]


def remember_token(name: str, pin: str) -> str:
    expires = int(time.time()) + REMEMBER_DAYS * 86400
    return f"{name}|{expires}|{_signature(name, pin, expires)}"


def restore_login(token: str):
    """Logs the person back in if their saved token is still valid.
    Changing someone's PIN or setting access to 'no' signs them out everywhere."""
    try:
        name, expires, sig = str(token).rsplit("|", 2)
        expires = int(expires)
    except ValueError:
        return
    if expires < time.time():
        return
    users = load("Users")
    match = users[(users["name"] == name) & (users["active"].str.lower() != "no")]
    if match.empty:
        return
    if hmac.compare_digest(sig, _signature(name, match.iloc[0]["pin"].strip(), expires)):
        st.session_state.user = name
        st.session_state.role = match.iloc[0]["role"].strip().lower()


# ---------------------------------------------------------------
# Screens
# ---------------------------------------------------------------
def login_screen():
    show_html(f'<div class="tt-hero"><div class="tt-mono">{MONOGRAM}</div>'
              f'<div class="tt-eyebrow">{esc(BUSINESS_NAME)}</div>'
              f'<h1>{esc(APP_NAME)}</h1><p>Sign in to see your tasks for today.</p></div>')
    people = active_people()
    if not people:
        st.error("No active users found. Open the Google Sheet, go to the Users tab and add one.")
        return
    users = load("Users")
    with st.form("login"):
        name = st.selectbox("Your name", people)
        pin = st.text_input("PIN", type="password", max_chars=8)
        if st.form_submit_button("Log in", type="primary"):
            match = users[users["name"] == name]
            if not match.empty and match.iloc[0]["pin"].strip() == pin.strip():
                st.session_state.user = name
                st.session_state.role = match.iloc[0]["role"].strip().lower()
                st.session_state.save_login = remember_token(name, match.iloc[0]["pin"].strip())
                st.rerun()
            else:
                st.error("Wrong PIN. Ask the owner if you forgot it.")


def today_tab(tasks, user, is_admin):
    scope = "My tasks"
    if is_admin:
        scope = st.radio("Show", ["My tasks", "Whole team"], horizontal=True, key="today_scope")
    df = tasks[(tasks["status"] != "Done") & (tasks["_due"] <= today())]
    if scope == "My tasks":
        df = for_person(df, user)
    overdue = (df["_due"] < today()).sum()
    pills = [f'<span class="count">{len(df)}</span>',
             f'<span class="lbl">task{"s" if len(df) != 1 else ""} for today</span>']
    if overdue:
        pills.append(f'<span class="late">{overdue} overdue</span>')
    show_html(f'<div class="tt-summary">{"".join(pills)}</div>')
    render_list(df, "today", user, is_admin, "Nothing due today. Check the All tab for upcoming work.")


def all_tab(tasks, user, is_admin):
    c1, c2 = st.columns(2)
    show = c1.radio("Status", ["Open", "Done", "All"], horizontal=True, key="all_status")
    areas = c2.multiselect("Area", area_list(), key="all_area", placeholder="All areas")
    if is_admin:
        person = st.selectbox("Person", ["Whole team"] + [EVERYONE] + active_people(), key="all_person")
    else:
        person = user

    df = tasks
    if show == "Open":
        df = df[df["status"] != "Done"]
    elif show == "Done":
        df = df[df["status"] == "Done"].sort_values("done_at", ascending=False)
    if areas:
        df = df[df["area"].isin(areas)]
    if person == user and not is_admin:
        df = for_person(df, user)
    elif person != "Whole team":
        df = df[df["assigned_to"] == person]
    render_list(df, "all", user, is_admin, "No tasks match these filters.")


def add_tab(user, is_admin):
    people = [EVERYONE] + active_people()
    with st.form("add_task", clear_on_submit=True):
        title = st.text_input("Task", placeholder="e.g. Upload new kids' T-shirt catalog on Meesho")
        area = st.selectbox("Area", area_list())
        assigned = st.selectbox("Assigned to", people, index=safe_index(people, user))
        priority = st.radio("Priority", PRIORITIES, index=1, horizontal=True)
        repeat = st.selectbox("Repeat", REPEATS,
                              help="Weekly repeats on the same weekday as the due date. "
                                   "Monthly repeats on the same date every month.")
        due = st.date_input("Due date", today(), format="DD/MM/YYYY")
        notes = st.text_area("Notes (optional)")
        if st.form_submit_button("Add task", type="primary", icon=":material/add:"):
            if not title.strip():
                st.error("Write the task name first.")
            else:
                add_task(title=title.strip(), area=area, repeat=repeat, priority=priority,
                         due_date=due.isoformat(), assigned_to=assigned, notes=notes,
                         created_by=user)
                st.success(f"Added: {title.strip()}")


def waiting_tab(tasks, user, is_admin):
    df = tasks[tasks["status"] == "Waiting"].copy()
    if not is_admin:
        df = for_person(df, user)
    df["_since"] = df["waiting_since"].apply(lambda s: parse_date(s) or today())
    df = df.sort_values("_since")
    st.caption("Things stuck because of someone else. Oldest first, so chase these.")
    render_list(df, "wait", user, is_admin, "Nothing is waiting on anyone right now.")


def dashboard_tab(tasks):
    t_str = today().isoformat()
    open_df = tasks[tasks["status"] != "Done"]
    overdue = open_df[open_df["_due"] < today()]
    done_today = tasks[(tasks["status"] == "Done") & tasks["done_at"].str.startswith(t_str)]
    waiting = open_df[open_df["status"] == "Waiting"]

    kpis = [
        ("Open", len(open_df), "radio_button_unchecked", False),
        ("Overdue", len(overdue), "error", len(overdue) > 0),
        ("Done today", len(done_today), "check_circle", False),
        ("Waiting", len(waiting), "hourglass_top", False),
    ]
    show_html('<div class="tt-kpis">', *[
        f'<div class="tt-kpi{" alert" if alert else ""}">'
        f'<div class="tt-kpi-label">{ic(icon)}{label}</div><div class="tt-kpi-num">{n}</div></div>'
        for label, n, icon, alert in kpis
    ], '</div>')

    st.subheader("Open tasks by area")
    if open_df.empty:
        empty_state("celebration", "No open tasks.")
    else:
        counts = open_df.groupby("area").size().sort_values(ascending=False)
        top = counts.max()
        show_html('<div class="tt-panel">', *[
            f'<div class="tt-bar-row" title="{esc(area)}: {n} open task{"s" if n != 1 else ""}">'
            f'<div class="tt-bar-label">{esc(area or "No area")}</div>'
            f'<div class="tt-bar-track"><div class="tt-bar" style="width:{n / top * 100:.0f}%"></div></div>'
            f'<div class="tt-bar-val">{n}</div></div>'
            for area, n in counts.items()
        ], '</div>')

    st.subheader("Team today")
    team = pd.DataFrame({
        "Open": open_df.groupby("assigned_to").size(),
        "Overdue": overdue.groupby("assigned_to").size(),
        "Done today": done_today.groupby("done_by").size(),
    }).fillna(0).astype(int)
    if team.empty:
        empty_state("groups", "No activity yet.")
    else:
        rows = []
        for person, r in team.sort_values("Overdue", ascending=False).iterrows():
            cells = []
            for col in ("Open", "Overdue", "Done today"):
                cls = "zero" if r[col] == 0 else ("late" if col == "Overdue" else "")
                cells.append(f'<td class="{cls}">{r[col]}</td>')
            rows.append(f'<tr><td>{esc(person or "Unassigned")}</td>{"".join(cells)}</tr>')
        show_html('<div class="tt-panel"><table class="tt-table"><thead><tr><th>Person</th><th>Open</th>'
                  '<th>Overdue</th><th>Done today</th></tr></thead><tbody>', *rows, '</tbody></table></div>')

    st.subheader("Completed today")
    if done_today.empty:
        empty_state("coffee", "Nothing completed yet today.")
    else:
        show_html('<div class="tt-panel">', *[
            f'<div class="tt-list-item"><div><div class="tt-list-main">{esc(r["title"])}</div>'
            f'<div class="tt-list-sub">{esc(r["area"])} · {esc(r["done_by"])}</div></div>'
            f'<div class="tt-list-side ok">{esc(r["done_at"][-5:])}</div></div>'
            for _, r in done_today.iterrows()
        ], '</div>')

    st.subheader("Overdue list")
    if overdue.empty:
        empty_state("verified", "No overdue tasks.")
    else:
        view = overdue.copy()
        view["late"] = view["_due"].apply(lambda d: (today() - d).days)
        show_html('<div class="tt-panel">', *[
            f'<div class="tt-list-item"><div><div class="tt-list-main">{esc(r["title"])}</div>'
            f'<div class="tt-list-sub">{esc(r["area"])} · {esc(r["assigned_to"])}</div></div>'
            f'<div class="tt-list-side late">{r["late"]}d late</div></div>'
            for _, r in view.sort_values("late", ascending=False).iterrows()
        ], '</div>')


def team_tab():
    users = load("Users")
    st.subheader("Team")
    st.dataframe(users[["name", "role", "active"]].rename(columns={
        "name": "Name", "role": "Role", "active": "Active"}), hide_index=True)

    with st.form("add_user", clear_on_submit=True):
        st.markdown("**Add staff**")
        name = st.text_input("Name")
        pin = st.text_input("PIN (4 digits, don't start with 0)", max_chars=8)
        role = st.radio("Role", ["staff", "admin"], horizontal=True,
                        help="Admin sees everyone's tasks, the dashboard and this Team tab.")
        if st.form_submit_button("Add person", icon=":material/person_add:"):
            if not name.strip() or not pin.strip():
                st.error("Enter both name and PIN.")
            elif name.strip() in users["name"].tolist():
                st.error("This name already exists.")
            else:
                ws("Users").append_row([name.strip(), pin.strip(), role, "yes"], value_input_option="RAW")
                refresh()
                st.success(f"Added {name.strip()}. Share the app link and their PIN with them.")

    with st.form("edit_user"):
        st.markdown("**Change PIN or remove access**")
        who = st.selectbox("Person", users["name"].tolist())
        new_pin = st.text_input("New PIN (leave empty to keep)", max_chars=8)
        active = st.radio("Access", ["yes", "no"], horizontal=True,
                          help="Choose 'no' when a staff member leaves. Their task history stays.")
        if st.form_submit_button("Save", type="primary"):
            fields = {"active": active}
            if new_pin.strip():
                fields["pin"] = new_pin.strip()
            if who == st.session_state.user and active == "no":
                st.error("You can't remove your own access.")
            elif update_fields("Users", who, fields):
                st.success(f"Updated {who}.")

    st.subheader("Business areas")
    st.caption(", ".join(area_list()))
    with st.form("add_area", clear_on_submit=True):
        new_area = st.text_input("New area", placeholder="e.g. Amazon, Photoshoot")
        if st.form_submit_button("Add area", icon=":material/add:") and new_area.strip():
            if new_area.strip() in area_list():
                st.error("This area already exists.")
            else:
                ws("Areas").append_row([new_area.strip()], value_input_option="RAW")
                refresh()
                st.success(f"Added area: {new_area.strip()}")


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main():
    try:
        ensure_setup()
    except Exception as e:
        st.error(
            "Could not connect to the Google Sheet. Check that: (1) Secrets are pasted in "
            "Streamlit settings, (2) the sheet is shared with the service account email as "
            "Editor, (3) Google Sheets API and Google Drive API are enabled."
        )
        st.caption(f"Technical detail: {e}")
        st.stop()

    if "user" not in st.session_state and not st.session_state.get("logged_out"):
        token = remember("read")
        if token:
            restore_login(token)
    if "user" not in st.session_state:
        if st.session_state.get("logged_out"):
            remember("clear")
        login_screen()
        st.stop()

    if "save_login" in st.session_state:
        remember("save", st.session_state.save_login)

    user = st.session_state.user
    is_admin = st.session_state.get("role") == "admin"

    with st.container(key="topbar"):
        h1, h2, h3 = st.columns([4, 1, 1])
        h1.markdown(
            f'<div class="tt-brand"><div class="tt-mono">{MONOGRAM}</div><div style="min-width:0">'
            f'<div class="tt-brand-name">Hi, {esc(user)}</div>'
            f'<div class="tt-brand-sub">{today().strftime("%a %d %b")} · {esc(BUSINESS_NAME)}</div>'
            f'</div></div>', unsafe_allow_html=True)
        if h2.button("", icon=":material/refresh:", key="refresh_btn", help="Refresh"):
            refresh()
            st.rerun()
        if h3.button("Log out", key="logout_btn"):
            st.session_state.clear()
            st.session_state.logged_out = True
            st.rerun()

    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))

    tasks = prepared_tasks()

    if is_admin:
        tabs = st.tabs([":material/today: Today", ":material/list: All", ":material/add: Add", ":material/schedule: Waiting",
                        ":material/insights: Dashboard", ":material/group: Team"])
    else:
        tabs = st.tabs([":material/today: Today", ":material/list: All", ":material/add: Add", ":material/schedule: Waiting"])

    with tabs[0]:
        today_tab(tasks, user, is_admin)
    with tabs[1]:
        all_tab(tasks, user, is_admin)
    with tabs[2]:
        add_tab(user, is_admin)
    with tabs[3]:
        waiting_tab(tasks, user, is_admin)
    if is_admin:
        with tabs[4]:
            dashboard_tab(tasks)
        with tabs[5]:
            team_tab()


main()
