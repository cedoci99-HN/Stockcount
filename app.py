# ERP AUDIT LEVEL 2 (FULL - KEEP ALL FEATURES + COUNTER/SUPERVISOR + LOCK + ADMIN EDIT + AUDIT LOG)

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

# ================= HELPER =================
def split_emp(text):
    emp_id = text.split(" - ")[0]
    name = text.split(" - ")[1].split(" (")[0]
    phone = text.split("(")[1].replace(")", "")
    return emp_id, name, phone

# ================= LOGIN =================
if not st.session_state.get("user"):
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    df_emp = pd.read_sql("SELECT * FROM employees", conn)
    emp_options = df_emp.apply(
        lambda x: f"{x['emp_id']} - {x['emp_name']} ({x['phone']})", axis=1
    ).tolist()

    st.markdown("### 👷 Thông tin ca kiểm kê")

    counter_select = st.selectbox("Counter", emp_options) if emp_options else st.text_input("Counter (ID - Name (Phone))")
    supervisor_select = st.selectbox("Supervisor", emp_options) if emp_options else st.text_input("Supervisor (ID - Name (Phone))")

    if st.button("Login"):
        df = pd.read_sql(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            conn,
            params=(username, password)
        )

        if not df.empty and counter_select and supervisor_select:
            st.session_state.user = username
            st.session_state.role = df.iloc[0]["role"]

            def add_emp(emp_text):
                emp_id, name, phone = split_emp(emp_text)
                c.execute("""
                INSERT INTO employees (emp_id, emp_name, phone)
                VALUES (%s,%s,%s)
                ON CONFLICT (emp_id) DO UPDATE
                SET emp_name=EXCLUDED.emp_name,
                    phone=EXCLUDED.phone
                """, (emp_id, name, phone))
                return emp_id, name, phone

            c_id, c_name, c_phone = add_emp(counter_select)
            s_id, s_name, s_phone = add_emp(supervisor_select)

            st.session_state.counter_id = c_id
            st.session_state.counter = c_name
            st.session_state.counter_phone = c_phone
            st.session_state.supervisor_id = s_id
            st.session_state.supervisor = s_name
            st.session_state.supervisor_phone = s_phone

            st.success("Login success")
            st.rerun()
        else:
            st.error("Thiếu thông tin")

    st.stop()

# ================= HEADER =================
st.title(f"📦 ERP Audit - {st.session_state.user}")
st.markdown(f"Counter: {st.session_state.get('counter','')} | Supervisor: {st.session_state.get('supervisor','')}")

# ================= LOCK =================
locked = is_locked()

if st.session_state.role == "admin":
    col1, col2 = st.columns(2)
    if col1.button("🔒 Lock"):
        set_lock(True)
        st.rerun()
    if col2.button("🔓 Unlock"):
        set_lock(False)
        st.rerun()

if locked and st.session_state.role != "admin":
    st.warning("🔒 System locked")

# ================= FORMS =================
forms = ["Component", "Scrap", "RM", "FG", "Regran"]
tabs = st.tabs(forms)

for i, tab in enumerate(tabs):
    with tab:
        item = st.text_input("Item", key=f"i_{i}")
        qty = st.number_input("Qty", key=f"q_{i}")
        loc = st.text_input("Location", key=f"l_{i}")

        if not (locked and st.session_state.role != "admin"):
            if st.button("Save", key=f"s_{i}"):
                c.execute("""
                INSERT INTO transactions (form,itemkey,quantity,location,created_by,
                counter_id,counter_name,counter_phone,
                supervisor_id,supervisor_name,supervisor_phone)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    forms[i], item, qty, loc, st.session_state.user,
                    st.session_state.counter_id,
                    st.session_state.counter,
                    st.session_state.counter_phone,
                    st.session_state.supervisor_id,
                    st.session_state.supervisor,
                    st.session_state.supervisor_phone
                ))
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

        new_qty = st.number_input("Qty", value=float(row["quantity"]))
        new_loc = st.text_input("Location", value=row["location"])

        if st.button("Update"):
            old_data = row.to_json()
            c.execute("UPDATE transactions SET quantity=%s, location=%s WHERE id=%s",
                      (new_qty, new_loc, selected_id))

            c.execute("INSERT INTO audit_log (trans_id,action,old_data,new_data,changed_by)
                      VALUES (%s,%s,%s,%s,%s)",
                      (selected_id, "UPDATE", old_data, str({"qty": new_qty}), st.session_state.user))

            st.success("Updated + Logged")
            st.rerun()

# ================= AUDIT =================
if st.session_state.role == "admin":
    st.markdown("## 📜 Audit Log")
    st.dataframe(pd.read_sql("SELECT * FROM audit_log ORDER BY changed_at DESC", conn))

# ================= DASHBOARD =================
df_all = pd.read_sql("SELECT * FROM transactions", conn)
if not df_all.empty:
    st.bar_chart(df_all.groupby("form")["quantity"].sum())