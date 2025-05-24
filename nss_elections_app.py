import streamlit as st
import sqlite3
import hashlib
import os

# --------- Utilities ---------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    if 'conn' not in st.session_state:
        st.session_state.conn = sqlite3.connect('nss_election.db', check_same_thread=False)
    return st.session_state.conn

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
        c.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            ('admin', hash_password('admin123'))
        )
    conn.commit()

# --------- DB Operations ---------
@st.cache_data(show_spinner=False)
def get_volunteer(student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT student_id, name, voted FROM volunteers WHERE student_id = ?", (student_id.lower().strip(),))
    vol = c.fetchone()
    return vol

@st.cache_data(show_spinner=False)
def get_candidates():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, photo_path, votes FROM candidates")
    candidates = c.fetchall()
    return candidates

@st.cache_data(show_spinner=False)
def get_results():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, votes FROM candidates ORDER BY votes DESC")
    results = c.fetchall()
    return results

def add_volunteer(student_id, name):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO volunteers (student_id, name) VALUES (?, ?)", (student_id.lower().strip(), name.strip()))
        conn.commit()
        # Clear cache after write
        get_volunteer.clear()
        return True
    except sqlite3.IntegrityError:
        return False

def mark_voted(student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE volunteers SET voted = 1 WHERE student_id = ?", (student_id.lower().strip(),))
    conn.commit()
    get_volunteer.clear()

def add_candidate(name, photo):
    os.makedirs("photos", exist_ok=True)
    filename = f"photos/{name.replace(' ', '_')}.png"
    with open(filename, "wb") as f:
        f.write(photo.getbuffer())
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO candidates (name, photo_path) VALUES (?, ?)", (name.strip(), filename))
    conn.commit()
    get_candidates.clear()

def vote_for_candidate(candidate_id, student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE candidates SET votes = votes + 1 WHERE id = ?", (candidate_id,))
    c.execute("UPDATE volunteers SET voted = 1 WHERE student_id = ?", (student_id.lower().strip(),))
    conn.commit()
    get_candidates.clear()
    get_volunteer.clear()

def check_admin_credentials(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM admin WHERE username = ? AND password = ?", (username, hash_password(password)))
    result = c.fetchone()
    return result is not None

# --------- Main ---------
st.set_page_config(page_title="NSS Elections", layout="centered")
st.title("📮 NSS Election Voting System")

init_db()

if 'volunteer_logged_in' not in st.session_state:
    st.session_state.volunteer_logged_in = False
if 'volunteer_info' not in st.session_state:
    st.session_state.volunteer_info = None
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False

menu = st.sidebar.selectbox("Select Mode", ["Volunteer Login", "Admin Login"])

if menu == "Volunteer Login":
    st.header("🎓 NSS Volunteer Login")

    if not st.session_state.volunteer_logged_in:
        student_id = st.text_input("Enter your Student ID").strip()
        if st.button("Login"):
            if not student_id:
                st.warning("Please enter your Student ID.")
            else:
                volunteer = get_volunteer(student_id)
                if not volunteer:
                    st.error("❌ You are not a registered NSS volunteer.")
                else:
                    st.session_state.volunteer_logged_in = True
                    st.session_state.volunteer_info = volunteer
                    st.experimental_rerun()
    else:
        student_id, name, voted = st.session_state.volunteer_info
        st.success(f"Welcome {name}!")

        if voted:
            st.info("You have already voted. Thank you!")
        else:
            st.info("Please cast your vote:")
            candidates = get_candidates()
            if not candidates:
                st.warning("No candidates available to vote for.")
            else:
                for cid, cname, photo, _ in candidates:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.image(photo, width=80)
                    with col2:
                        if st.button(f"Vote for {cname}", key=f"vote_{cid}"):
                            vote_for_candidate(cid, student_id)
                            st.success(f"✅ Vote recorded for {cname}. Thank you for voting!")
                            st.session_state.volunteer_info = (student_id, name, 1)
                            st.experimental_rerun()

        if st.button("Logout"):
            st.session_state.volunteer_logged_in = False
            st.session_state.volunteer_info = None
            st.experimental_rerun()

elif menu == "Admin Login":
    st.header("🔐 Admin Login")

    if not st.session_state.admin_logged_in:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if check_admin_credentials(username, password):
                st.session_state.admin_logged_in = True
                st.experimental_rerun()
            else:
                st.error("❌ Invalid admin credentials.")
    else:
        st.success("Admin logged in!")

        st.subheader("➕ Register NSS Volunteer")
        with st.form("volunteer_form"):
            vol_id = st.text_input("Student ID").strip()
            vol_name = st.text_input("Full Name").strip()
            submitted = st.form_submit_button("Add Volunteer")
            if submitted:
                if vol_id and vol_name:
                    if add_volunteer(vol_id, vol_name):
                        st.success("Volunteer added successfully.")
                    else:
                        st.warning("This Student ID is already registered.")
                else:
                    st.warning("Please provide both Student ID and Name.")

        st.markdown("---")

        st.subheader("➕ Add Candidate")
        with st.form("candidate_form"):
            cand_name = st.text_input("Candidate Name").strip()
            cand_photo = st.file_uploader("Upload Candidate Photo", type=["png", "jpg", "jpeg"])
            submitted = st.form_submit_button("Add Candidate")
            if submitted:
                if cand_name and cand_photo:
                    add_candidate(cand_name, cand_photo)
                    st.success("Candidate added successfully.")
                else:
                    st.warning("Please enter candidate name and upload photo.")

        st.markdown("---")

        st.subheader("❌ Remove Candidate")
        candidates = get_candidates()
        if candidates:
            for cid, cname, photo, _ in candidates:
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    st.image(photo, width=60)
                with col2:
                    st.write(cname)
                with col3:
                    if st.button(f"Remove", key=f"remove_{cid}"):
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("DELETE FROM candidates WHERE id = ?", (cid,))
                        conn.commit()
                        if os.path.exists(photo):
                            os.remove(photo)
                        get_candidates.clear()
                        st.success(f"Candidate '{cname}' removed successfully.")
                        st.experimental_rerun()
        else:
            st.info("No candidates to remove.")

        st.markdown("---")

        st.subheader("📊 Election Results")
        results = get_results()
        if results:
            for name, votes in results:
                st.info(f"{name} - {votes} vote(s)")
        else:
            st.info("No candidates or votes yet.")

        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.experimental_rerun()
