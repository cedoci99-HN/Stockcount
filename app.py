import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
from io import BytesIO
import streamlit.components.v1 as components

# ======================
# CONFIG
# ======================
st.set_page_config(page_title="Stock System", layout="centered")

# ======================
# CSS MOBILE
# ======================
st.markdown("""
<style>
.block-container { padding: 1rem; }
.stButton>button {
    width: 100%;
    height: 55px;
    font-size: 18px;
    border-radius: 12px;
}
input { font-size:18px !important; height:45px !important; }
.card {
    padding:15px;
    border-radius:15px;
    background:#f2f2f2;
    margin-bottom:10px;
}
</style>
""", unsafe_allow_html=True)

# ======================
# DB
# ======================
conn = psycopg2.connect(
    "postgresql://neondb_owner:npg_wILnY7suT1Pd@ep-weathered-surf-a1c5jl7b-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)
conn.autocommit = True
c = conn.cursor()
# ======================
# TABLES
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
CREATE TABLE IF NOT EXISTS locked_dates (
    lock_date DATE PRIMARY KEY,
    locked_by TEXT
);
""")

# ======================
# DEFAULT USER
# ======================
c.execute("""
INSERT INTO users VALUES ('admin','123','admin')
ON CONFLICT DO NOTHING;
""")

# ======================
# SESSION INIT
# ======================
if "user" not in st.session_state:
    st.session_state.user = None

# ======================
# HELPER
# ======================
def split_emp(text):
    emp_id = text.split(" - ")[0]
    name = text.split(" - ")[1].split(" (")[0]
    phone = text.split("(")[1].replace(")", "")
    return emp_id, name, phone

# ======================
# BARCODE SCANNER FIXED
# ======================
def barcode_scanner(key):
    return components.html(f"""
    <script src="https://unpkg.com/html5-qrcode"></script>
    <div id="reader_{key}" style="width:100%"></div>

    <script>
    function onScanSuccess(decodedText) {{
        const streamlitEvent = new Event("streamlit:setComponentValue");
        window.parent.postMessage({{
            type: "streamlit:setComponentValue",
            key: "{key}",
            value: decodedText
        }}, "*");
    }}

    new Html5QrcodeScanner("reader_{key}", {{ fps: 10, qrbox: 250 }})
        .render(onScanSuccess);
    </script>
    """, height=300)

# ======================
# LOGIN
# ======================
if not st.session_state.user:

    st.title("🔐 Login")

    user = st.text_input("User")
    pw = st.text_input("Password", type="password")

    df_emp = pd.read_sql("SELECT * FROM employees", conn)
    options = df_emp.apply(lambda x: f"{x.emp_id} - {x.emp_name} ({x.phone})", axis=1).tolist()

    mode = st.radio("Counter:", ["Dropdown","Gõ tay"])
    counter = st.selectbox("Counter", options) if mode=="Dropdown" and options else st.text_input("Counter")

    mode2 = st.radio("Supervisor:", ["Dropdown","Gõ tay"])
    sup = st.selectbox("Supervisor", options) if mode2=="Dropdown" and options else st.text_input("Supervisor")

    if st.button("Login"):

        df = pd.read_sql("SELECT * FROM users WHERE username=%s AND password=%s", conn, params=(user,pw))

        if not df.empty:

            def upsert(emp):
                eid,name,phone = split_emp(emp)
                c.execute("""
                INSERT INTO employees VALUES (%s,%s,%s)
                ON CONFLICT (emp_id) DO UPDATE
                SET emp_name=%s, phone=%s
                """,(eid,name,phone,name,phone))
                return eid,name,phone

            c_id,c_name,c_phone = upsert(counter)
            s_id,s_name,s_phone = upsert(sup)

            st.session_state.user = user
            st.session_state.role = df.iloc[0].role
            st.session_state.counter = c_name
            st.session_state.counter_id = c_id
            st.session_state.counter_phone = c_phone
            st.session_state.sup = s_name
            st.session_state.sup_id = s_id
            st.session_state.sup_phone = s_phone

            st.rerun()

    st.stop()

# ======================
# HEADER
# ======================
st.markdown(f"""
<div class="card">
📦 {st.session_state.user}<br>
👷 {st.session_state.counter}<br>
🧑‍💼 {st.session_state.sup}
</div>
""", unsafe_allow_html=True)

# ======================
# FORMS
# ======================
forms = ["Component","Scrap","RM","FG","Regran"]
tabs = st.tabs(forms)

for i,f in enumerate(forms):
    with tabs[i]:

        st.subheader(f)

        if f"barcode_{i}" not in st.session_state:
            st.session_state[f"barcode_{i}"] = ""

        st.markdown("### 📷 Scan Barcode")
        barcode_scanner(f"scan_{i}")

        item = st.text_input("Item / Barcode", value=st.session_state[f"barcode_{i}"], key=f"i_{i}")

        qty = st.number_input("Quantity", min_value=0.0, key=f"q_{i}")
        loc = st.text_input("Location", key=f"l_{i}")

        if st.button("💾 SAVE", key=f"save_{i}"):

            if not item:
                st.error("Chưa có barcode")
                st.stop()

            c.execute("""
            INSERT INTO transactions 
            (form,itemkey,quantity,location,created_by,
             counter_id,counter_name,counter_phone,
             supervisor_id,supervisor_name,supervisor_phone)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                f,item,qty,loc,st.session_state.user,
                st.session_state.counter_id,
                st.session_state.counter,
                st.session_state.counter_phone,
                st.session_state.sup_id,
                st.session_state.sup,
                st.session_state.sup_phone
            ))

            st.success("Saved")
            st.session_state[f"barcode_{i}"] = ""
            st.rerun()

# ======================
# DASHBOARD (GIỮ NGUYÊN)
# ======================
st.markdown("## 📊 Dashboard")
df_all = pd.read_sql("SELECT * FROM transactions", conn)
if not df_all.empty:
    st.bar_chart(df_all.groupby("form")["quantity"].sum())