"""
Team Task Tracker for Fusstees & KMR Garments
Works on phone + desktop. Data is stored in your Google Sheet.

You do NOT need to edit this file. Settings (staff, areas) are managed
inside the app (Team tab) or directly in the Google Sheet.
"""

import calendar
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st

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
PRIORITY_ICON = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}

st.set_page_config(page_title=APP_NAME, page_icon="✅", layout="centered")


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

    with st.container(border=True):
        icon = PRIORITY_ICON.get(t["priority"], "⚪")
        title = f"~~{t['title']}~~" if status == "Done" else t["title"]
        st.markdown(f"{icon} **{title}**")

        info = [f"📁 {t['area']}", f"👤 {t['assigned_to']}", f"📅 {nice_date(due)}"]
        if t["repeat"] in ("Daily", "Weekly", "Monthly"):
            info.append(f"🔁 {t['repeat']}")
        st.caption("   ".join(info))

        if status != "Done" and due and due < today():
            days = (today() - due).days
            st.markdown(f":red[**Overdue by {days} day{'s' if days > 1 else ''}**]")
        if status == "Doing":
            st.markdown(":blue[In progress]")
        if status == "Waiting":
            since = parse_date(t["waiting_since"])
            days = (today() - since).days if since else 0
            st.markdown(f":orange[⏳ Waiting on {t['waiting_on'] or 'someone'} for {days} day{'s' if days != 1 else ''}]")
        if t["notes"]:
            st.caption(f"📝 {t['notes']}")
        if status == "Done":
            st.caption(f"✅ Done by {t['done_by']} at {t['done_at']}")
            return

        c1, c2, c3, c4 = st.columns(4)
        if c1.button("✅ Done", key=f"{key}_done", type="primary"):
            complete_task(t, user)
            st.session_state.flash = f"Done: {t['title']}"
            st.rerun()

        if status == "To Do":
            if c2.button("▶️ Start", key=f"{key}_start"):
                update_fields("Tasks", tid, {"status": "Doing"})
                st.rerun()
        elif status == "Waiting":
            if c2.button("▶️ Resume", key=f"{key}_resume"):
                update_fields("Tasks", tid, {"status": "Doing", "waiting_on": "", "waiting_since": ""})
                st.rerun()

        if status != "Waiting":
            with c3.popover("⏳ Waiting"):
                who = st.text_input("Waiting on whom or what?", key=f"{key}_who",
                                    placeholder="e.g. Ravi supplier, fabric delivery")
                if st.button("Save", key=f"{key}_wait_save"):
                    update_fields("Tasks", tid, {"status": "Waiting", "waiting_on": who,
                                                 "waiting_since": today().isoformat()})
                    st.rerun()

        if is_admin:
            with c4.popover("✏️ Edit"):
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
        if st.form_submit_button("💾 Save changes"):
            update_fields("Tasks", t["id"], {
                "title": title.strip() or t["title"], "area": area, "assigned_to": assigned,
                "priority": priority, "repeat": repeat, "due_date": due.isoformat(), "notes": notes,
            })
            st.rerun()
    sure = st.checkbox("Yes, delete this task", key=f"{key}_sure")
    if st.button("🗑️ Delete task", key=f"{key}_delete", disabled=not sure):
        delete_task(t["id"])
        st.rerun()


def render_list(df: pd.DataFrame, prefix: str, user: str, is_admin: bool, empty_msg: str, limit: int = 100):
    if df.empty:
        st.info(empty_msg)
        return
    if len(df) > limit:
        st.caption(f"Showing first {limit} of {len(df)} tasks. Use the filters to narrow down.")
    for _, row in df.head(limit).iterrows():
        render_task(row.to_dict(), prefix, user, is_admin)


# ---------------------------------------------------------------
# Screens
# ---------------------------------------------------------------
def login_screen():
    st.title(f"✅ {APP_NAME}")
    st.caption(BUSINESS_NAME)
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
    st.caption(f"{len(df)} task{'s' if len(df) != 1 else ''} for today"
               + (f", {overdue} overdue" if overdue else ""))
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
        if st.form_submit_button("➕ Add task", type="primary"):
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

    c1, c2 = st.columns(2)
    c1.metric("Open tasks", len(open_df))
    c2.metric("Overdue", len(overdue))
    c3, c4 = st.columns(2)
    c3.metric("Done today", len(done_today))
    c4.metric("Waiting", len(waiting))

    st.subheader("Open tasks by area")
    if open_df.empty:
        st.info("No open tasks.")
    else:
        st.bar_chart(open_df.groupby("area").size().rename("Open tasks"))

    st.subheader("Team today")
    team = pd.DataFrame({
        "Open": open_df.groupby("assigned_to").size(),
        "Overdue": overdue.groupby("assigned_to").size(),
        "Done today": done_today.groupby("done_by").size(),
    }).fillna(0).astype(int)
    if team.empty:
        st.info("No activity yet.")
    else:
        st.dataframe(team.sort_values("Overdue", ascending=False))

    st.subheader("Completed today")
    if done_today.empty:
        st.caption("Nothing completed yet today.")
    else:
        st.dataframe(
            done_today[["title", "area", "done_by", "done_at"]].rename(columns={
                "title": "Task", "area": "Area", "done_by": "Done by", "done_at": "Time"}),
            hide_index=True,
        )

    st.subheader("Overdue list")
    if overdue.empty:
        st.caption("No overdue tasks.")
    else:
        view = overdue.copy()
        view["Days late"] = view["_due"].apply(lambda d: (today() - d).days)
        st.dataframe(
            view[["title", "area", "assigned_to", "Days late"]].rename(columns={
                "title": "Task", "area": "Area", "assigned_to": "Person"}),
            hide_index=True,
        )


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
        if st.form_submit_button("➕ Add person"):
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
        if st.form_submit_button("💾 Save"):
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
        if st.form_submit_button("➕ Add area") and new_area.strip():
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

    if "user" not in st.session_state:
        login_screen()
        st.stop()

    user = st.session_state.user
    is_admin = st.session_state.get("role") == "admin"

    h1, h2, h3 = st.columns([3, 1, 1])
    h1.markdown(f"### ✅ Hi, {user}")
    if h2.button("🔄 Refresh"):
        refresh()
        st.rerun()
    if h3.button("Log out"):
        st.session_state.clear()
        st.rerun()

    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))

    tasks = prepared_tasks()

    if is_admin:
        tabs = st.tabs(["📅 Today", "📋 All", "➕ Add", "⏳ Waiting", "📊 Dashboard", "👥 Team"])
    else:
        tabs = st.tabs(["📅 Today", "📋 All", "➕ Add", "⏳ Waiting"])

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
