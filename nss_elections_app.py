import streamlit as st
import sqlite3
import hashlib
import os
import pandas as pd
import io

# ---------- Utility Functions ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    conn = sqlite3.connect('nss_election.db', check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS volunteers (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            voted INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            photo_path TEXT,
            votes INTEGER DEFAULT 0
        )
    ''')
    c.execute("SELECT * FROM admin WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admin (username, password) VALUES (?, ?)",
                  ('admin', hash_password('admin123')))
    conn.commit()
    conn.close()

init_db()

# ---------- Database Operations ----------
def add_volunteer(student_id, name):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO volunteers (student_id, name) VALUES (?, ?)",
                  (student_id.lower().strip(), name.strip()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_volunteer(student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT student_id, name, voted FROM volunteers WHERE student_id = ?",
              (student_id.lower().strip(),))
    vol = c.fetchone()
    conn.close()
    return vol

def mark_voted(student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE volunteers SET voted = 1 WHERE student_id = ?",
              (student_id.lower().strip(),))
    conn.commit()
    conn.close()

def add_candidate(name, photo):
    os.makedirs("photos", exist_ok=True)
    filename = f"photos/{name.replace(' ', '_')}.png"
    with open(filename, "wb") as f:
        f.write(photo.getbuffer())
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO candidates (name, photo_path) VALUES (?, ?)",
              (name.strip(), filename))
    conn.commit()
    conn.close()

def get_candidates():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, photo_path, votes FROM candidates")
    candidates = c.fetchall()
    conn.close()
    return candidates

def vote_for_candidate(candidate_id, student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE candidates SET votes = votes + 1 WHERE id = ?", (candidate_id,))
    c.execute("UPDATE volunteers SET voted = 1 WHERE student_id = ?",
              (student_id.lower().strip(),))
    conn.commit()
    conn.close()

def delete_candidate(candidate_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
    conn.commit()
    conn.close()

def delete_volunteer(student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM volunteers WHERE student_id = ?", (student_id.lower().strip(),))
    conn.commit()
    conn.close()

def check_admin_credentials(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM admin WHERE username = ? AND password = ?",
              (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_results():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, votes FROM candidates ORDER BY votes DESC")
    results = c.fetchall()
    conn.close()
    return results

def get_volunteers_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM volunteers", conn)
    conn.close()
    return df

def get_candidates_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, name, photo_path, votes FROM candidates", conn)
    conn.close()
    return df

def get_results_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT name, votes FROM candidates ORDER BY votes DESC", conn)
    conn.close()
    return df

def to_excel(df, sheet_name='Sheet1'):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# ---------- Streamlit UI ----------
st.set_page_config(page_title="NSS Elections", layout="centered")
st.title("📮 NSS Election Voting System")

if 'volunteer_logged_in' not in st.session_state:
    st.session_state['volunteer_logged_in'] = False
if 'volunteer_info' not in st.session_state:
    st.session_state['volunteer_info'] = None
if 'admin_logged_in' not in st.session_state:
    st.session_state['admin_logged_in'] = False

menu = st.sidebar.selectbox("Select Mode", ["Volunteer Login", "Admin Login"])

# Volunteer Login & Voting
if menu == "Volunteer Login":
    st.header("🎓 NSS Volunteer Login")

    if not st.session_state['volunteer_logged_in']:
        student_id = st.text_input("Enter your Student ID")
        if st.button("Login"):
            if not student_id:
                st.warning("Please enter your Student ID.")
            else:
                volunteer = get_volunteer(student_id)
                if not volunteer:
                    st.error("❌ You are not a registered NSS volunteer.")
                else:
                    st.session_state['volunteer_logged_in'] = True
                    st.session_state['volunteer_info'] = volunteer
                    st.rerun()
    else:
        student_id, name, voted = st.session_state['volunteer_info']
        st.success(f"Welcome {name}!")

        if voted:
            st.info("You have already voted. Thank you!")
        else:
            st.info("Please cast your vote:")
            candidates = get_candidates()
            if not candidates:
                st.warning("No candidates available.")
            else:
                for cid, cname, photo, _ in candidates:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.image(photo, width=80)
                    with col2:
                        if st.button(f"Vote for {cname}", key=f"vote_{cid}"):
                            vote_for_candidate(cid, student_id)
                            st.success(f"✅ Vote recorded for {cname}.")
                            st.session_state['volunteer_info'] = (student_id, name, 1)
                            st.rerun()

        if st.button("Logout"):
            st.session_state['volunteer_logged_in'] = False
            st.session_state['volunteer_info'] = None
            st.rerun()

# Admin Login & Dashboard
elif menu == "Admin Login":
    st.header("🔐 Admin Login")

    if not st.session_state['admin_logged_in']:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if check_admin_credentials(username, password):
                st.session_state['admin_logged_in'] = True
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")
    else:
        st.success("Admin logged in.")

        st.subheader("➕ Register NSS Volunteer")
        with st.form("volunteer_form"):
            vol_id = st.text_input("Student ID")
            vol_name = st.text_input("Full Name")
            if st.form_submit_button("Add Volunteer"):
                if vol_id and vol_name:
                    if add_volunteer(vol_id, vol_name):
                        st.success("Volunteer added.")
                    else:
                        st.warning("Student ID already exists.")
                else:
                    st.warning("Please fill all fields.")

        st.markdown("---")

        st.subheader("➕ Add Candidate")
        with st.form("candidate_form"):
            cand_name = st.text_input("Candidate Name")
            cand_photo = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
            if st.form_submit_button("Add Candidate"):
                if cand_name and cand_photo:
                    add_candidate(cand_name, cand_photo)
                    st.success("Candidate added.")
                else:
                    st.warning("Fill both name and photo.")

        st.markdown("---")

        st.subheader("🗑️ Remove Candidate")
        candidates = get_candidates()
        for cid, cname, _, _ in candidates:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{cname}")
            with col2:
                if st.button(f"Remove", key=f"del_cand_{cid}"):
                    delete_candidate(cid)
                    st.success(f"Deleted {cname}")
                    st.rerun()

        st.markdown("---")

        st.subheader("🗑️ Remove Volunteer")
        volunteers = get_volunteers_df()
        if not volunteers.empty:
            for idx, row in volunteers.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{row['student_id']} - {row['name']}")
                with col2:
                    if st.button(f"Remove", key=f"del_vol_{row['student_id']}"):
                        delete_volunteer(row['student_id'])
                        st.success(f"Deleted volunteer {row['student_id']}")
                        st.rerun()
        else:
            st.info("No volunteers registered.")

        st.markdown("---")

        st.subheader("📊 View Results")
        results_df = get_results_df()
        if not results_df.empty:
            st.dataframe(results_df)
        else:
            st.info("No votes recorded yet.")

        st.markdown("---")

        st.subheader("📥 Download Data")
        vol_df = get_volunteers_df()
        cand_df = get_candidates_df()
        res_df = get_results_df()

        col1, col2, col3 = st.columns(3)
        with col1:
            excel_vol = to_excel(vol_df, "Volunteers")
            st.download_button(
                label="Download Volunteers Excel",
                data=excel_vol,
                file_name="volunteers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            excel_cand = to_excel(cand_df, "Candidates")
            st.download_button(
                label="Download Candidates Excel",
                data=excel_cand,
                file_name="candidates.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col3:
            excel_res = to_excel(res_df, "Results")
            st.download_button(
                label="Download Results Excel",
                data=excel_res,
                file_name="results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        if st.button("Logout"):
            st.session_state['admin_logged_in'] = False
            st.rerun()
