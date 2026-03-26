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
# MOBILE UI CSS
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
input, .stTextInput input {
    font-size: 18px !important;
    height: 45px !important;
}
.card {
    padding: 15px;
    border-radius: 15px;
    background-color: #f2f2f2;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ======================
# DB CONNECT
# ======================
conn = psycopg2.connect("YOUR_DB_URL")
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
CREATE TABLE IF NOT EXISTS locked_dates (
    lock_date DATE PRIMARY KEY,
    locked_by TEXT
);
""")

c.execute("""
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    action TEXT,
    trans_id INT,
    old_data TEXT,
    new_data TEXT,
    updated_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# ======================
# DEFAULT USER
# ======================
c.execute("""
INSERT INTO users VALUES
('admin','123','admin')
ON CONFLICT DO NOTHING;
""")

# ======================
# SESSION
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
# BARCODE SCANNER
# ======================
def barcode_scanner():
    html = """
    <script src="https://unpkg.com/html5-qrcode"></script>
    <div id="reader"></div>
    <script>
    function onScanSuccess(decodedText) {
        var audio = new Audio("https://www.soundjay.com/buttons/beep-07.mp3");
        audio.play();
        window.parent.postMessage({type:"streamlit:setComponentValue",value:decodedText},"*");
    }
    let scanner = new Html5QrcodeScanner("reader",{fps:10,qrbox:250});
    scanner.render(onScanSuccess);
    </script>
    """
    return components.html(html, height=300)

# ======================
# LOGIN
# ======================
if not st.session_state.user:

    st.title("🔐 Login")

    user = st.text_input("User")
    pw = st.text_input("Password", type="password")

    df_emp = pd.read_sql("SELECT * FROM employees", conn)
    options = df_emp.apply(lambda x: f"{x.emp_id} - {x.emp_name} ({x.phone})", axis=1).tolist()

    mode = st.radio("Counter nhập:", ["Dropdown","Gõ tay"])
    counter = st.selectbox("Counter", options) if mode=="Dropdown" and options else st.text_input("Counter")

    mode2 = st.radio("Supervisor nhập:", ["Dropdown","Gõ tay"])
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
# FORM + SCAN
# ======================
forms = ["RM","FG","Scrap"]
tabs = st.tabs(forms)

for i,f in enumerate(forms):
    with tabs[i]:

        st.subheader(f)

        scan = barcode_scanner()
        item = st.text_input("Item / Barcode", key=f"i{i}")

        qty = st.number_input("Qty", 0.0, key=f"q{i}")
        loc = st.text_input("Location", key=f"l{i}")

        if scan:
            item = scan
            st.success(f"Scanned {item}")

        if st.button("💾 SAVE", key=f"s{i}"):

            # check lock
            lock = pd.read_sql("SELECT * FROM locked_dates WHERE lock_date=%s",
                               conn, params=(datetime.today().date(),))
            if not lock.empty:
                st.error("Date locked")
                st.stop()

            c.execute("""
            INSERT INTO transactions
            (form,itemkey,quantity,location,created_by,
            counter_id,counter_name,counter_phone,
            supervisor_id,supervisor_name,supervisor_phone)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,(f,item,qty,loc,st.session_state.user,
                 st.session_state.counter_id,
                 st.session_state.counter,
                 st.session_state.counter_phone,
                 st.session_state.sup_id,
                 st.session_state.sup,
                 st.session_state.sup_phone))

            st.success("Saved")
            st.rerun()

# ======================
# FILTER
# ======================
st.markdown("## 🔎 Search")

df = pd.read_sql("SELECT * FROM transactions", conn)

if not df.empty:
    df["created_at"] = pd.to_datetime(df["created_at"])

    d1 = st.date_input("From", df.created_at.min().date())
    d2 = st.date_input("To", df.created_at.max().date())

    user = st.selectbox("User", ["All"]+df.created_by.unique().tolist())

    df = df[(df.created_at.dt.date>=d1)&(df.created_at.dt.date<=d2)]
    if user!="All":
        df = df[df.created_by==user]

    st.dataframe(df)

    # export
    st.download_button("CSV", df.to_csv(index=False), "data.csv")

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        df.to_excel(w,index=False)
    st.download_button("Excel", bio.getvalue(), "data.xlsx")

# ======================
# ADMIN
# ======================
if st.session_state.role=="admin":

    st.markdown("## 🔒 Lock Date")
    d = st.date_input("Lock date")
    if st.button("Lock"):
        c.execute("INSERT INTO locked_dates VALUES (%s,%s) ON CONFLICT DO NOTHING",
                  (d,st.session_state.user))

    st.markdown("## ✏️ Edit")

    tid = st.number_input("ID",1)
    newq = st.number_input("New Qty",0.0)

    if st.button("Update"):
        old = pd.read_sql("SELECT * FROM transactions WHERE id=%s", conn, params=(tid,))
        c.execute("UPDATE transactions SET quantity=%s WHERE id=%s",(newq,tid))

        c.execute("""
        INSERT INTO audit_log (action,trans_id,old_data,new_data,updated_by)
        VALUES (%s,%s,%s,%s,%s)
        """,("UPDATE",tid,old.to_json(),str(newq),st.session_state.user))

        st.success("Updated")

# ======================
# DASHBOARD
# ======================
st.markdown("## 📊 Trend")

df = pd.read_sql("""
SELECT DATE(created_at) d, SUM(quantity) q
FROM transactions GROUP BY d ORDER BY d
""", conn)

if not df.empty:
    df = df.set_index("d")
    st.line_chart(df)