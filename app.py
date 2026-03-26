import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
from io import BytesIO

# ======================
# CONFIG
# ======================
st.set_page_config(page_title="Stock System", layout="centered")

# ======================
# CONNECT DB
# ======================
conn = psycopg2.connect(
    "postgresql://neondb_owner:npg_wILnY7suT1Pd@ep-weathered-surf-a1c5jl7b-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)
conn.autocommit = True
c = conn.cursor()

# ======================
# CREATE TABLES
# ======================
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

# ======================
# DEFAULT USERS
# ======================
c.execute("""
INSERT INTO users (username,password,role) VALUES
('admin','123','admin'),
('user1','user1','user'),
('user2','user2','user'),
('user3','user3','user')
ON CONFLICT (username) DO NOTHING;
""")

# ======================
# SESSION INIT
# ======================
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

# ======================
# HELPER
# ======================
def split_emp(text):
    """Chia chuỗi kiểu 'ID - Name (Phone)'"""
    emp_id = text.split(" - ")[0]
    name = text.split(" - ")[1].split(" (")[0]
    phone = text.split("(")[1].replace(")", "")
    return emp_id, name, phone

# ======================
# LOGIN
# ======================
if not st.session_state.get("user"):
    st.title("🔐 Login")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    # load employee
    df_emp = pd.read_sql("SELECT * FROM employees", conn)
    emp_options = df_emp.apply(
        lambda x: f"{x['emp_id']} - {x['emp_name']} ({x['phone']})", axis=1
    ).tolist()

    st.markdown("### 👷 Thông tin ca kiểm kê")

    # Nếu có nhân sự → dropdown, nếu chưa có → text input
    if len(emp_options) > 0:
        counter_select = st.selectbox("Counter", emp_options, key="counter_select")
        supervisor_select = st.selectbox("Supervisor", emp_options, key="supervisor_select")
    else:
        counter_select = st.text_input("Counter (gõ tay: ID - Name (Phone))", key="counter_text")
        supervisor_select = st.text_input("Supervisor (gõ tay: ID - Name (Phone))", key="supervisor_text")

    if st.button("Login", key="btn_login"):
        df = pd.read_sql(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            conn,
            params=(username, password)
        )

        if not df.empty and counter_select and supervisor_select:
            st.session_state.user = username
            st.session_state.role = df.iloc[0]["role"]

            # Nếu chưa có trong bảng employees thì tự thêm
            def add_emp(emp_text):
                if " - " in emp_text and "(" in emp_text:
                    emp_id, name, phone = split_emp(emp_text)
                    # kiểm tra có chưa
                    df_check = pd.read_sql("SELECT * FROM employees WHERE emp_id=%s", conn, params=(emp_id,))
                    if df_check.empty:
                        c.execute("""
                        INSERT INTO employees (emp_id, emp_name, phone)
                        VALUES (%s,%s,%s)
                        """, (emp_id, name, phone))
                    return emp_id, name, phone
                else:
                    st.error("Nhập nhân sự phải theo format: ID - Name (Phone)")
                    st.stop()

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
            st.error("Sai tài khoản hoặc thiếu thông tin")

    st.stop()

# ======================
# HEADER
# ======================
st.title(f"📦 Stock System - {st.session_state.get('user','')}")
st.markdown(f"""
👷 Counter: **{st.session_state.get('counter','')}**  
🧑‍💼 Supervisor: **{st.session_state.get('supervisor','')}**
""")

if st.button("Logout", key="btn_logout"):
    st.session_state.user = None
    st.rerun()

# ======================
# ADMIN - USER MGMT
# ======================
if st.session_state.get('role') == "admin":
    st.markdown("## 👤 User Management")
    df_users = pd.read_sql("SELECT * FROM users", conn)
    st.dataframe(df_users)

    new_user = st.text_input("Username", key="admin_new_user")
    new_pass = st.text_input("Password", key="admin_new_pass")
    new_role = st.selectbox("Role", ["admin", "user"], key="admin_new_role")
    if st.button("Save User", key="btn_save_user"):
        c.execute("""
        INSERT INTO users (username,password,role)
        VALUES (%s,%s,%s)
        ON CONFLICT (username) DO UPDATE
        SET password=EXCLUDED.password,
            role=EXCLUDED.role;
        """, (new_user, new_pass, new_role))
        st.success("Saved")

# ======================
# UPLOAD EMPLOYEE
# ======================
st.markdown("## 👷 Upload Employee")
file_emp = st.file_uploader("Employee Excel", type=["xlsx"], key="upl_emp")
if file_emp:
    df_emp = pd.read_excel(file_emp)
    if st.button("Save Employees", key="btn_save_emp"):
        for _, row in df_emp.iterrows():
            c.execute("""
            INSERT INTO employees (emp_id, emp_name, phone)
            VALUES (%s,%s,%s)
            ON CONFLICT (emp_id) DO UPDATE
            SET emp_name=EXCLUDED.emp_name,
                phone=EXCLUDED.phone;
            """, (
                row["EmpID"],
                row["Name"],
                row["Phone"]
            ))
        st.success("Done")

# ======================
# UPLOAD ITEM MASTER
# ======================
st.markdown("## 📦 Upload Item Master")
file = st.file_uploader("Item Master Excel", type=["xlsx"], key="upl_item")
if file:
    df_master = pd.read_excel(file)
    if st.button("Save Item Master", key="btn_save_item"):
        for _, row in df_master.iterrows():
            c.execute("""
            INSERT INTO item_master (itemkey, description, unit)
            VALUES (%s,%s,%s)
            ON CONFLICT (itemkey) DO UPDATE
            SET description=EXCLUDED.description,
                unit=EXCLUDED.unit;
            """, (
                row["Itemkey"],
                row["Description"],
                row["Unit"]
            ))
        st.success("Done")

# ======================
# LOAD ITEMS
# ======================
df_items = pd.read_sql("SELECT * FROM item_master", conn)
def search_items(keyword):
    if not keyword:
        return df_items.head(50)
    return df_items[df_items["itemkey"].str.contains(keyword, case=False)]

# ======================
# FORMS
# ======================
forms = ["Component", "Scrap", "RM", "FG", "Regran"]
tabs = st.tabs(forms)

for i, tab in enumerate(tabs):
    with tab:
        st.subheader(forms[i])

        keyword = st.text_input("🔍 Search Item", key=f"s_{i}")
        filtered = search_items(keyword)

        item = st.selectbox("Item", filtered["itemkey"].tolist(), key=f"i_{i}")
        barcode = st.text_input("📷 Barcode", key=f"b_{i}")
        if barcode:
            item = barcode

        qty = st.number_input("Quantity", min_value=0.0, key=f"q_{i}")
        loc = st.text_input("Location", key=f"l_{i}")

        if st.button("Save", key=f"save_{i}"):
            c.execute("""
            INSERT INTO transactions 
            (form,itemkey,quantity,location,created_by,
             counter_id,counter_name,counter_phone,
             supervisor_id,supervisor_name,supervisor_phone)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                forms[i], item, qty, loc, st.session_state.get('user',''),
                st.session_state.get('counter_id',''),
                st.session_state.get('counter',''),
                st.session_state.get('counter_phone',''),
                st.session_state.get('supervisor_id',''),
                st.session_state.get('supervisor',''),
                st.session_state.get('supervisor_phone','')
            ))
            st.success("Saved")

        df = pd.read_sql(f"SELECT * FROM transactions WHERE form='{forms[i]}'", conn)
        st.dataframe(df)
        if not df.empty:
            csv = df.to_csv(index=False).encode()
            st.download_button("Download CSV", csv, key=f"download_{i}")

# ======================
# DASHBOARD
# ======================
st.markdown("## 📊 Dashboard")
df_all = pd.read_sql("SELECT * FROM transactions", conn)
if not df_all.empty:
    st.bar_chart(df_all.groupby("form")["quantity"].sum())