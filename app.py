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
# CONNECT DB (NEON)
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

c.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    action TEXT,
    username TEXT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# default admin
c.execute("""
INSERT INTO users (username,password,role) VALUES
('admin','123','admin'),
('user1','user1','user'),
('user2','user2','user'),
('user3','user3','user')
ON CONFLICT (username) DO NOTHING;
""")

# ======================
# LOGIN
# ======================
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

if not st.session_state.user:
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

            c.execute("INSERT INTO logs (action, username) VALUES (%s,%s)",
                      ("Login", username))

            st.success("Login success")
            st.rerun()
        else:
            st.error("Sai tài khoản")

    st.stop()

# ======================
# HEADER
# ======================
st.title(f"📦 Stock System - {st.session_state.user}")

if st.button("Logout"):
    st.session_state.user = None
    st.rerun()

# ======================
# UPLOAD ITEM MASTER
# ======================
st.markdown("## 📦 Upload Item Master")

file = st.file_uploader("Upload Excel Item Master", type=["xlsx"])

if file:
    df_master = pd.read_excel(file)

    if st.button("💾 Save Item Master"):
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

        st.success("Upload thành công!")

# ======================
# LOAD ITEM LIST
# ======================
df_items = pd.read_sql("SELECT * FROM item_master", conn)

# ======================
# SEARCH FUNCTION
# ======================
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

        if st.session_state.role != "viewer":

            # 🔍 SEARCH BOX
            keyword = st.text_input("🔍 Search Item", key=f"search_{i}")

            filtered = search_items(keyword)

            item = st.selectbox(
                "Chọn Item",
                filtered["itemkey"].tolist(),
                key=f"item_{i}"
            )

            # 📷 BARCODE INPUT
            barcode = st.text_input("📷 Scan Barcode", key=f"barcode_{i}")

            if barcode:
                item = barcode

            qty = st.number_input("Quantity", min_value=0.0, key=f"qty_{i}")
            loc = st.text_input("Location", key=f"loc_{i}")

            if st.button("💾 Save", key=f"save_{i}"):

                if not item:
                    st.error("Chọn Item")
                else:
                    c.execute("""
                    INSERT INTO transactions (form,itemkey,quantity,location,created_by)
                    VALUES (%s,%s,%s,%s,%s)
                    """, (forms[i], item, qty, loc, st.session_state.user))

                    c.execute("""
                    INSERT INTO logs (action, username)
                    VALUES (%s,%s)
                    """, (f"Insert {forms[i]}", st.session_state.user))

                    st.success(f"Saved: {item}")

        # ======================
        # FILTER
        # ======================
        st.markdown("### 🔍 Filter")

        date_filter = st.date_input("Date", datetime.today(), key=f"d_{i}")
        loc_filter = st.text_input("Location", key=f"l_{i}")
        item_filter = st.text_input("Itemkey", key=f"f_{i}")

        query = "SELECT * FROM transactions WHERE form=%s AND DATE(created_at)=%s"
        params = [forms[i], date_filter]

        if loc_filter:
            query += " AND location=%s"
            params.append(loc_filter)

        if item_filter:
            query += " AND itemkey=%s"
            params.append(item_filter)

        df = pd.read_sql(query, conn, params=params)

        st.dataframe(df, use_container_width=True)

        # EXPORT
        if not df.empty:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 CSV", csv, f"{forms[i]}.csv")

            output = BytesIO()
            df.to_excel(output, index=False, engine="openpyxl")

            st.download_button("📥 Excel", output.getvalue(), f"{forms[i]}.xlsx")

# ======================
# DASHBOARD
# ======================
st.markdown("## 📊 Dashboard")

df_all = pd.read_sql("SELECT * FROM transactions", conn)

if not df_all.empty:
    st.bar_chart(df_all.groupby("form")["quantity"].sum())
    st.bar_chart(df_all.groupby("location")["quantity"].sum())

# ======================
# LOG
# ======================
if st.session_state.role == "admin":
    st.markdown("## 📜 Logs")
    df_log = pd.read_sql("SELECT * FROM logs ORDER BY time DESC", conn)
    st.dataframe(df_log, use_container_width=True)