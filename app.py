# app.py
import streamlit as st
from datetime import date, datetime
import sqlite3
from typing import List, Tuple, Optional
import pandas as pd

DB_PATH = "todos.db"  # when deploying to a cloud env you might switch to a hosted DB

# ---------- DB helpers ----------
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT,
            due_date TEXT,
            completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

def add_todo(title: str, description: str, priority: str, due_date: Optional[str]):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO todos (title, description, priority, due_date) VALUES (?, ?, ?, ?)",
        (title, description, priority, due_date),
    )
    conn.commit()
    conn.close()

def update_todo(todo_id: int, title: str, description: str, priority: str, due_date: Optional[str]):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE todos SET title=?, description=?, priority=?, due_date=? WHERE id=?",
        (title, description, priority, due_date, todo_id),
    )
    conn.commit()
    conn.close()

def set_completed(todo_id: int, completed: bool):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE todos SET completed=? WHERE id=?", (1 if completed else 0, todo_id))
    conn.commit()
    conn.close()

def delete_todo(todo_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM todos WHERE id=?", (todo_id,))
    conn.commit()
    conn.close()

def fetch_todos() -> List[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM todos ORDER BY completed, priority DESC, due_date IS NULL, due_date")
    rows = c.fetchall()
    conn.close()
    return rows

# ---------- UI and App logic ----------
st.set_page_config(page_title="✨ Streamlit To-Do", page_icon="📋", layout="wide")
init_db()

st.title("📋 Streamlit To-Do — build, track, ship")

# top row: add task form
with st.expander("➕ Add a new task", expanded=True):
    with st.form("add_todo_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 3, 1])
        with col1:
            title = st.text_input("Task title", placeholder="e.g. Prepare report")
        with col2:
            description = st.text_area("Description (optional)", height=45, placeholder="Add details...")
        with col3:
            priority = st.selectbox("Priority", ["Medium", "High", "Low"], index=0)
            due = st.date_input("Due date (optional)", value=None)
            # date_input returns today's date if given default; we treat a checkbox to enable due date
        enable_due = st.checkbox("Set a due date", value=False)
        if not enable_due:
            due_date_value = None
        else:
            due_date_value = st.date_input("Choose due date", value=date.today())
        submitted = st.form_submit_button("Add task")
        if submitted:
            if not title.strip():
                st.error("Task title is required.")
            else:
                due_str = due_date_value.isoformat() if due_date_value else None
                add_todo(title.strip(), description.strip(), priority, due_str)
                st.success("Task added ✅")
                st.experimental_rerun()

# Controls: search / filters / sort
st.markdown("---")
controls_col1, controls_col2, controls_col3 = st.columns([2, 1, 1])
with controls_col1:
    q = st.text_input("Search tasks (title/description)", "")
with controls_col2:
    show_completed = st.checkbox("Show completed", value=True)
with controls_col3:
    priority_filter = st.multiselect("Filter priority", options=["High", "Medium", "Low"], default=["High", "Medium", "Low"])

# fetch tasks
todos = fetch_todos()
df = pd.DataFrame([dict(r) for r in todos]) if todos else pd.DataFrame(columns=["id", "title", "description", "priority", "due_date", "completed", "created_at"])

# apply search and filters
def filter_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    filtered = df.copy()
    if q:
        qlow = q.lower()
        mask = filtered["title"].str.lower().str.contains(qlow) | filtered["description"].str.lower().str.contains(qlow)
        filtered = filtered[mask]
    if not show_completed:
        filtered = filtered[filtered["completed"] == 0]
    if priority_filter:
        filtered = filtered[filtered["priority"].isin(priority_filter)]
    return filtered

filtered = filter_df(df)

st.write(f"### Tasks ({len(filtered)})")
if filtered.empty:
    st.info("No tasks found. Add your first task above.")
else:
    # display tasks as cards in columns
    for idx, row in filtered.iterrows():
        cols = st.columns([6, 1, 1])
        with st.container():
            # Left: task info
            title_line = f"**{row['title']}**"
            if row["completed"]:
                title_line = f"~~{title_line}~~ ✅"
            st.markdown(title_line)
            md = ""
            if row.get("description"):
                md += row["description"] + "\n\n"
            if row.get("due_date"):
                # highlight overdue
                try:
                    due_dt = datetime.fromisoformat(row["due_date"]).date()
                except Exception:
                    due_dt = None
                if due_dt:
                    if due_dt < date.today() and not row["completed"]:
                        md += f"**Due:** {due_dt.isoformat()} ⏰ (overdue)\n\n"
                    else:
                        md += f"**Due:** {due_dt.isoformat()}\n\n"
            md += f"**Priority:** {row['priority']}\n\n"
            md += f"**Created:** {row['created_at']}"
            st.write(md)

            # Right: action buttons (complete toggle, edit, delete)
            but_complete = cols[1].checkbox("Done", value=bool(row["completed"]), key=f"done_{row['id']}")
            if but_complete != bool(row["completed"]):
                set_completed(row["id"], but_complete)
                st.experimental_rerun()

            # Edit and Delete as small buttons
            c1, c2 = st.columns([1,1])
            if c1.button("Edit", key=f"edit_{row['id']}"):
                # show edit modal-like form
                with st.form(f"edit_form_{row['id']}"):
                    new_title = st.text_input("Title", value=row["title"])
                    new_desc = st.text_area("Description", value=row["description"] or "")
                    new_priority = st.selectbox("Priority", ["High","Medium","Low"], index=["High","Medium","Low"].index(row["priority"]))
                    has_due = bool(row["due_date"])
                    new_has_due = st.checkbox("Has due date", value=has_due)
                    if new_has_due:
                        try:
                            cur_due = date.fromisoformat(row["due_date"]) if row["due_date"] else date.today()
                        except Exception:
                            cur_due = date.today()
                        new_due = st.date_input("Due date", value=cur_due)
                        new_due_str = new_due.isoformat()
                    else:
                        new_due_str = None
                    save = st.form_submit_button("Save")
                    if save:
                        if not new_title.strip():
                            st.error("Title required")
                        else:
                            update_todo(row["id"], new_title.strip(), new_desc.strip(), new_priority, new_due_str)
                            st.success("Updated")
                            st.experimental_rerun()
            if c2.button("Delete", key=f"del_{row['id']}"):
                delete_todo(row["id"])
                st.warning("Deleted")
                st.experimental_rerun()

st.markdown("---")
st.caption("Built with ❤️ using Streamlit — simple, local SQLite persistence by default.")

# Footer: helpful buttons
st.sidebar.header("Quick actions")
if st.sidebar.button("Clear completed"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM todos WHERE completed=1")
    conn.commit()
    conn.close()
    st.sidebar.success("Cleared completed tasks")
    st.experimental_rerun()

if st.sidebar.button("Export tasks (CSV)"):
    todos_all = fetch_todos()
    df_export = pd.DataFrame([dict(r) for r in todos_all])
    csv = df_export.to_csv(index=False)
    st.sidebar.download_button("Download CSV", csv, file_name="todos.csv", mime="text/csv")
