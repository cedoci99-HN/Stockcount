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
c.execute("""
INSERT INTO users (username,password,role) VALUES
('admin','123','admin')
ON CONFLICT (username) DO NOTHING;
""")

# ✅ NEW: LOCK TABLE
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

# ======================
# LOCK FUNCTIONS
# ======================
def is_locked():
    return pd.read_sql("SELECT is_locked FROM app_control WHERE id=1", conn).iloc[0][0]

def set_lock(val):
    c.execute("UPDATE app_control SET is_locked=%s WHERE id=1", (val,))
    
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

    # --------- Counter ---------
    st.markdown("#### Counter")
    counter_choice = st.radio("Chọn kiểu nhập Counter:", ["Chọn trong danh sách", "Gõ tay"], key="counter_type")
    if counter_choice == "Chọn trong danh sách" and emp_options:
        counter_select = st.selectbox("Counter", emp_options, key="counter_select")
    else:
        counter_select = st.text_input("Counter (ID - Name (Phone))", key="counter_text")

    # --------- Supervisor ---------
    st.markdown("#### Supervisor")
    supervisor_choice = st.radio("Chọn kiểu nhập Supervisor:", ["Chọn trong danh sách", "Gõ tay"], key="supervisor_type")
    if supervisor_choice == "Chọn trong danh sách" and emp_options:
        supervisor_select = st.selectbox("Supervisor", emp_options, key="supervisor_select")
    else:
        supervisor_select = st.text_input("Supervisor (ID - Name (Phone))", key="supervisor_text")

    if st.button("Login", key="btn_login"):
        df = pd.read_sql(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            conn,
            params=(username, password)
        )

        if not df.empty and counter_select and supervisor_select:
            st.session_state.user = username
            st.session_state.role = df.iloc[0]["role"]

            # Hàm thêm hoặc cập nhật nhân viên
            def add_or_update_emp(emp_text):
                if " - " in emp_text and "(" in emp_text:
                    emp_id, name, phone = split_emp(emp_text)
                    df_check = pd.read_sql("SELECT * FROM employees WHERE emp_id=%s", conn, params=(emp_id,))
                    if df_check.empty:
                        # Thêm mới
                        c.execute("""
                        INSERT INTO employees (emp_id, emp_name, phone)
                        VALUES (%s,%s,%s)
                        """, (emp_id, name, phone))
                    else:
                        # Cập nhật nếu thông tin thay đổi
                        if df_check.iloc[0]["emp_name"] != name or df_check.iloc[0]["phone"] != phone:
                            c.execute("""
                            UPDATE employees SET emp_name=%s, phone=%s
                            WHERE emp_id=%s
                            """, (name, phone, emp_id))
                    return emp_id, name, phone
                else:
                    st.error("Nhập nhân sự phải theo format: ID - Name (Phone)")
                    st.stop()

            c_id, c_name, c_phone = add_or_update_emp(counter_select)
            s_id, s_name, s_phone = add_or_update_emp(supervisor_select)

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
    
#Thêm biến điều hướng (sau login)
if "page" not in st.session_state:
    st.session_state.page = "main"

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
#Main page
if st.session_state.page == "main":
    st.markdown("## 🏠 Main Menu")

    col1, col2, col3 = st.columns(3)

    if col1.button("📥 Input Data"):
        st.session_state.page = "input"
        st.rerun()

    if col2.button("🔎 Search"):
        st.session_state.page = "search"
        st.rerun()

    if col3.button("📊 Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    if st.session_state.role == "admin":
        if st.button("⚙️ Admin Panel"):
            st.session_state.page = "admin"
            st.rerun()

    st.stop()
# ======================
# LOCK STATUS DISPLAY
# ======================
locked = is_locked()

if locked:
    st.error("🔒 SYSTEM STATUS: LOCKED")
else:
    st.success("🔓 SYSTEM STATUS: UNLOCKED")
    
# ======================
# LOAD ITEMS
# ======================
df_items = pd.read_sql("SELECT * FROM item_master", conn)
def search_items(keyword):
    if not keyword:
        return df_items.head(50)
    return df_items[df_items["itemkey"].str.contains(keyword, case=False)]
    
#PAGE INPUT (tabs của bạn)
if st.session_state.page == "input":

    if st.button("⬅️ Back"):
        st.session_state.page = "main"
        st.rerun()

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
            
     # 🚫 BLOCK IF LOCKED
            if locked and st.session_state.role != "admin":
                st.warning("🔒 System locked - cannot input")
            else:
                if st.button("Save", key=f"save_btn_{forms[i]}_{i}"):
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

            # Hiển thị table với counter & supervisor đầy đủ
            df = pd.read_sql(f"SELECT * FROM transactions WHERE form='{forms[i]}'", conn)
            st.dataframe(df)

            # Export CSV/Excel
            if not df.empty:
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, file_name=f"{forms[i]}_transactions.csv", mime="text/csv")

                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                st.download_button(
                    "Download Excel",
                    output.getvalue(),
                    file_name=f"{forms[i]}_transactions.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
#PAGE SEARCH
if st.session_state.page == "search":

    if st.button("⬅️ Back"):
        st.session_state.page = "main"
        st.rerun()

    # ======================
    # SEARCH / FILTER
    # ======================
    st.markdown("## 🔎 Search Transactions")

    df_all = pd.read_sql("SELECT * FROM transactions", conn)

    if not df_all.empty:
        # Convert datetime
        df_all["created_at"] = pd.to_datetime(df_all["created_at"])

        col1, col2, col3 = st.columns(3)

        with col1:
            date_from = st.date_input("From Date", value=df_all["created_at"].min().date())
        with col2:
            date_to = st.date_input("To Date", value=df_all["created_at"].max().date())
        with col3:
            users = ["All"] + df_all["created_by"].dropna().unique().tolist()
            user_filter = st.selectbox("User", users)

        # Apply filter
        df_filter = df_all[
            (df_all["created_at"].dt.date >= date_from) &
            (df_all["created_at"].dt.date <= date_to)
        ]

        if user_filter != "All":
            df_filter = df_filter[df_filter["created_by"] == user_filter]

        st.dataframe(df_filter)

        # Export sau khi filter
        if not df_filter.empty:
            # CSV
            csv = df_filter.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV (Filtered)",
                csv,
                file_name="filtered_transactions.csv",
                mime="text/csv"
            )

            # Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_filter.to_excel(writer, index=False, sheet_name='Filtered')
            st.download_button(
                "Download Excel (Filtered)",
                output.getvalue(),
                file_name="filtered_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    else:
        st.info("No data available")
#PAGE DASHBOARD
if st.session_state.page == "dashboard":

    if st.button("⬅️ Back"):
        st.session_state.page = "main"
        st.rerun()

    # ======================
    # DASHBOARD
    # ======================
    st.markdown("## 📊 Dashboard")
    df_all = pd.read_sql("SELECT * FROM transactions", conn)
    if not df_all.empty:
        st.bar_chart(df_all.groupby("form")["quantity"].sum())
#PAGE ADMIN
if st.session_state.page == "admin":

    if st.button("⬅️ Back"):
        st.session_state.page = "main"
        st.rerun()

    #st.markdown("## ⚙️ Admin Panel")

    # 👉 user management + upload + edit transaction

    # ======================
    # ADMIN LOCK CONTROL
    # ======================
    if st.session_state.role == "admin":
        st.markdown("## 🔒 System Control")

        col1, col2 = st.columns(2)

        if col1.button("🔒 Lock System"):
            set_lock(True)
            st.rerun()

        if col2.button("🔓 Unlock System"):
            set_lock(False)
            st.rerun()

    # ======================
    # ADMIN - USER MGMT & UPLOAD MASTER/EMP
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

        # Upload Employee (admin only)
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

        # Upload Item Master (admin only)
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
    # ADMIN EDIT TRANSACTION
    # ======================
    if st.session_state.get("role") == "admin":
        st.markdown("## ✏️ Edit Transaction (Admin)")

        df_edit = pd.read_sql("SELECT * FROM transactions ORDER BY id DESC", conn)

        if not df_edit.empty:
            # chọn transaction
            selected_id = st.selectbox("Chọn Transaction ID", df_edit["id"])

            row = df_edit[df_edit["id"] == selected_id].iloc[0]

            # hiển thị info cũ
            st.markdown(f"""
            **Item:** {row['itemkey']}  
            **Form:** {row['form']}  
            **Created by:** {row['created_by']}  
            """)

            # chỉnh sửa
            new_qty = st.number_input("Quantity", value=float(row["quantity"]), key="edit_qty")
            new_loc = st.text_input("Location", value=row["location"], key="edit_loc")

            col1, col2 = st.columns(2)

            # update
            if col1.button("💾 Update Transaction"):
                c.execute("""
                UPDATE transactions
                SET quantity=%s,
                    location=%s
                WHERE id=%s
                """, (new_qty, new_loc, selected_id))

                st.success("✅ Updated successfully")
                st.rerun()

            # delete (optional)
            if col2.button("🗑 Delete Transaction"):
                c.execute("DELETE FROM transactions WHERE id=%s", (selected_id,))
                st.warning("Deleted")
                st.rerun()
        else:
            st.info("No data to edit")