# ERP AUDIT LEVEL 2 (FULL - KEEP ALL FEATURES + LOCK + ADMIN EDIT + AUDIT LOG)

import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="ERP Audit", layout="centered")

# ================= DB =================
conn = psycopg2.connect(
    "postgresql://neondb_owner:npg_wILnY7suT1Pd@ep-weathered-surf-a1c5jl7b-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)
conn.autocommit = True
c = conn.cursor()

# ================= TABLES =================
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    role TEXT
);
""")

c.execute("""
CREATE TABLE IF NOT EXISTS employees (
    emp_id TEXT PRIMARY KEY,
    emp_name TEXT,
    phone TEXT
);
""")

c.execute("""
CREATE TABLE IF NOT EXISTS item_master (
    itemkey TEXT PRIMARY KEY,
    description TEXT,
    unit TEXT
);
""")

c.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    form TEXT,
    itemkey TEXT,
    quantity FLOAT,
    location TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    counter_id TEXT,
    counter_name TEXT,
    counter_phone TEXT,
    supervisor_id TEXT,
    supervisor_name TEXT,
    supervisor_phone TEXT
);
""")

# NEW: audit log
c.execute("""
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    trans_id INT,
    action TEXT,
    old_data TEXT,
    new_data TEXT,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# NEW: lock control
c.execute("""
CREATE TABLE IF NOT EXISTS app_control (
    id INT PRIMARY KEY,
    is_locked BOOLEAN
);
""")

c.execute("""
INSERT INTO app_control (id, is_locked)
VALUES (1, FALSE)
ON CONFLICT (id) DO NOTHING;
""")

# ================= LOCK =================
def is_locked():
    return pd.read_sql("SELECT is_locked FROM app_control WHERE id=1", conn).iloc[0][0]

def set_lock(val):
    c.execute("UPDATE app_control SET is_locked=%s WHERE id=1", (val,))

# ================= SESSION =================
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

# ================= LOGIN =================
if not st.session_state.get("user"):
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        df = pd.read_sql(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            conn,
            params=(username, password)
        )

        if not df.empty:
            st.session_state.user = username
            st.session_state.role = df.iloc[0]["role"]
            st.success("Login success")
            st.rerun()
        else:
            st.error("Sai tài khoản")

    st.stop()

# ================= HEADER =================
st.title(f"📦 ERP Audit - {st.session_state.user}")

if st.button("Logout"):
    st.session_state.user = None
    st.rerun()

# ================= LOCK STATUS =================
locked = is_locked()

if locked and st.session_state.role != "admin":
    st.warning("🔒 System đang bị khóa")

# ================= ADMIN CONTROL =================
if st.session_state.role == "admin":
    st.markdown("## 🔧 Admin Control")

    col1, col2 = st.columns(2)
    if col1.button("🔒 Lock App"):
        set_lock(True)
        st.rerun()
    if col2.button("🔓 Unlock App"):
        set_lock(False)
        st.rerun()

# ================= LOAD ITEMS =================
df_items = pd.read_sql("SELECT * FROM item_master", conn)

def search_items(keyword):
    if not keyword:
        return df_items.head(50)
    return df_items[df_items["itemkey"].str.contains(keyword, case=False)]

# ================= FORMS =================
forms = ["Component", "Scrap", "RM", "FG", "Regran"]
tabs = st.tabs(forms)

for i, tab in enumerate(tabs):
    with tab:
        st.subheader(forms[i])

        keyword = st.text_input("Search Item", key=f"s_{i}")
        filtered = search_items(keyword)

        item = st.selectbox("Item", filtered["itemkey"].tolist(), key=f"i_{i}")
        qty = st.number_input("Quantity", min_value=0.0, key=f"q_{i}")
        loc = st.text_input("Location", key=f"l_{i}")

        if locked and st.session_state.role != "admin":
            st.warning("🔒 Locked - cannot input")
        else:
            if st.button("Save", key=f"save_{i}"):
                c.execute("""
                INSERT INTO transactions (form,itemkey,quantity,location,created_by)
                VALUES (%s,%s,%s,%s,%s)
                """, (forms[i], item, qty, loc, st.session_state.user))
                st.success("Saved")

        df = pd.read_sql(f"SELECT * FROM transactions WHERE form='{forms[i]}'", conn)
        st.dataframe(df)

# ================= ADMIN EDIT =================
if st.session_state.role == "admin":
    st.markdown("## ✏️ Edit Transaction")

    df_edit = pd.read_sql("SELECT * FROM transactions", conn)

    if not df_edit.empty:
        selected_id = st.selectbox("ID", df_edit["id"])
        row = df_edit[df_edit["id"] == selected_id].iloc[0]

        new_qty = st.number_input("Quantity", value=float(row["quantity"]))
        new_loc = st.text_input("Location", value=row["location"])

        if st.button("Update"):
            old_data = row.to_json()

            c.execute("""
            UPDATE transactions SET quantity=%s, location=%s WHERE id=%s
            """, (new_qty, new_loc, selected_id))

            new_data = {"qty": new_qty, "loc": new_loc}

            c.execute("""
            INSERT INTO audit_log (trans_id, action, old_data, new_data, changed_by)
            VALUES (%s,%s,%s,%s,%s)
            """, (selected_id, "UPDATE", old_data, str(new_data), st.session_state.user))

            st.success("Updated + Logged")
            st.rerun()

# ================= AUDIT LOG VIEW =================
if st.session_state.role == "admin":
    st.markdown("## 📜 Audit Log")
    df_log = pd.read_sql("SELECT * FROM audit_log ORDER BY changed_at DESC", conn)
    st.dataframe(df_log)

# ================= EXPORT =================
df_all = pd.read_sql("SELECT * FROM transactions", conn)

if not df_all.empty:
    csv = df_all.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "transactions.csv")

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_all.to_excel(writer, index=False)
    st.download_button("Download Excel", output.getvalue(), "transactions.xlsx")

# ================= DASHBOARD =================
if not df_all.empty:
    st.markdown("## 📊 Dashboard")
    st.bar_chart(df_all.groupby("form")["quantity"].sum())