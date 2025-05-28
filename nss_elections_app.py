import streamlit as st
import sqlite3
import hashlib
import pandas as pd

# ----------------------------------
# DB Helpers
# ----------------------------------
def get_db_connection():
    conn = sqlite3.connect('nss_election.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_tables():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS volunteers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        roll_number TEXT UNIQUE,
        phone_number TEXT,
        year TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        roll_number TEXT UNIQUE,
        year TEXT,
        position1 TEXT,
        position2 TEXT,
        photo BLOB
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        volunteer_id INTEGER,
        candidate_id INTEGER,
        position TEXT,
        FOREIGN KEY (volunteer_id) REFERENCES volunteers(id),
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )''')

    conn.commit()
    conn.close()

def create_admin():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM admin")
    if not c.fetchone():
        c.execute("INSERT INTO admin (username, password) VALUES (?, ?)", 
                  ('admin', hash_password('admin123')))
        conn.commit()
    conn.close()

def check_admin_credentials(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM admin WHERE username = ? AND password = ?", 
              (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result

def get_volunteer_by_roll(roll_number):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM volunteers WHERE roll_number = ?", (roll_number,))
    result = c.fetchone()
    conn.close()
    return result

def has_voted(volunteer_id, position):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM votes WHERE volunteer_id = ? AND position = ?", 
              (volunteer_id, position))
    result = c.fetchone()
    conn.close()
    return result is not None

def submit_vote(volunteer_id, candidate_id, position):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO votes (volunteer_id, candidate_id, position) VALUES (?, ?, ?)", 
              (volunteer_id, candidate_id, position))
    conn.commit()
    conn.close()

def get_unique_positions():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT DISTINCT position1 FROM candidates WHERE position1 IS NOT NULL "
        "UNION "
        "SELECT DISTINCT position2 FROM candidates WHERE position2 IS NOT NULL"
    )
    positions = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    return sorted(positions)

def get_votes_csv():
    conn = get_db_connection()
    query = '''
        SELECT 
            v.roll_number AS volunteer_roll,
            c.name AS candidate_name,
            vt.position AS position
        FROM votes vt
        JOIN volunteers v ON vt.volunteer_id = v.id
        JOIN candidates c ON vt.candidate_id = c.id
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_all_volunteers():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM volunteers", conn)
    conn.close()
    return df

def get_all_candidates():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT name, roll_number, year, position1, position2 FROM candidates", conn)
    conn.close()
    return df

def get_vote_counts():
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT c.name AS candidate, vt.position, COUNT(*) AS votes
        FROM votes vt
        JOIN candidates c ON vt.candidate_id = c.id
        GROUP BY vt.candidate_id, vt.position
    """, conn)
    conn.close()
    return df

def remove_volunteer(roll):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM volunteers WHERE roll_number = ?", (roll,))
    conn.commit()
    conn.close()

def remove_candidate(roll):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM candidates WHERE roll_number = ?", (roll,))
    conn.commit()
    conn.close()

# ----------------------------------
# Session State Initialization
# ----------------------------------
def init_session_state():
    if "admin_user" not in st.session_state:
        st.session_state.admin_user = ""
    if "admin_password" not in st.session_state:
        st.session_state.admin_password = ""
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False
    if "volunteer_logged_in" not in st.session_state:
        st.session_state.volunteer_logged_in = False
    if "volunteer_id" not in st.session_state:
        st.session_state.volunteer_id = None
    if "volunteer_name" not in st.session_state:
        st.session_state.volunteer_name = ""
    if "user_votes" not in st.session_state:
        st.session_state.user_votes = {}

# ----------------------------------
# Admin Login Page
# ----------------------------------
def admin_login_page():
    st.title("🗳️ NSS Election System - Admin Login")
    st.text_input("Username", key="admin_user")
    st.text_input("Password", type="password", key="admin_password")

    if st.button("Login"):
        if check_admin_credentials(st.session_state.admin_user, st.session_state.admin_password):
            st.session_state.admin_logged_in = True
            st.success("✅ Login Successful")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

# ----------------------------------
# Admin Panel Page
# ----------------------------------
def admin_panel_page():
    st.title("Admin Panel - NSS Election System")
    st.write(f"Welcome, **{st.session_state.admin_user}**")

    # Volunteer Add Section
    st.subheader("👥 Add Volunteer")
    with st.form("add_volunteer_form", clear_on_submit=True):
        name = st.text_input("Name")
        roll_number = st.text_input("Roll Number")
        phone = st.text_input("Phone Number")
        year = st.selectbox("Year", ["1st", "2nd", "3rd", "4th"])
        submitted_vol = st.form_submit_button("Add Volunteer")
        if submitted_vol:
            conn = get_db_connection()
            c = conn.cursor()
            try:
                c.execute("INSERT INTO volunteers (name, roll_number, phone_number, year) VALUES (?, ?, ?, ?)",
                          (name, roll_number, phone, year))
                conn.commit()
                st.success("Volunteer added successfully")
            except Exception as e:
                st.error(f"Error: {e}")
            conn.close()

    # Candidate Add Section
    st.subheader("🧑‍💼 Add Candidate")
    with st.form("add_candidate_form", clear_on_submit=True):
        cname = st.text_input("Candidate Name")
        croll = st.text_input("Candidate Roll Number")
        cyear = st.selectbox("Candidate Year", ["1st", "2nd", "3rd", "4th"])
        position1 = st.text_input("Position 1")
        position2 = st.text_input("Position 2 (optional)")
        photo = st.file_uploader("Upload Photo", type=["jpg", "jpeg", "png"])
        submitted_cand = st.form_submit_button("Add Candidate")
        if submitted_cand:
            conn = get_db_connection()
            c = conn.cursor()
            try:
                photo_bytes = photo.read() if photo else None
                c.execute("INSERT INTO candidates (name, roll_number, year, position1, position2, photo) VALUES (?, ?, ?, ?, ?, ?)",
                          (cname, croll, cyear, position1, position2, photo_bytes))
                conn.commit()
                st.success("Candidate added successfully")
            except Exception as e:
                st.error(f"Error: {e}")
            conn.close()

    # Downloads
    st.subheader("📊 Downloads")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### Volunteers")
        dfv = get_all_volunteers()
        st.download_button("Download Volunteers", dfv.to_csv(index=False), "volunteers.csv")
    with col2:
        st.markdown("### Candidates")
        dfc = get_all_candidates()
        st.download_button("Download Candidates", dfc.to_csv(index=False), "candidates.csv")
    with col3:
        st.markdown("### Votes")
        dfvotes = get_votes_csv()
        st.download_button("Download Votes", dfvotes.to_csv(index=False), "votes.csv")

    # Remove Volunteers or Candidates
    st.subheader("🗑️ Remove Volunteer or Candidate")

    volunteers = get_all_volunteers().to_dict(orient='records')
    candidates = get_all_candidates().to_dict(orient='records')

    st.markdown("**Volunteers:**")
    vol_rolls = [v['roll_number'] for v in volunteers]
    vol_to_remove = st.selectbox("Select Volunteer Roll Number to Remove", [""] + vol_rolls)
    if st.button("Remove Volunteer") and vol_to_remove:
        remove_volunteer(vol_to_remove)
        st.success(f"Removed volunteer with roll {vol_to_remove}")
        st.rerun()

    st.markdown("**Candidates:**")
    cand_rolls = [c['roll_number'] for c in candidates]
    cand_to_remove = st.selectbox("Select Candidate Roll Number to Remove", [""] + cand_rolls)
    if st.button("Remove Candidate") and cand_to_remove:
        remove_candidate(cand_to_remove)
        st.success(f"Removed candidate with roll {cand_to_remove}")
        st.rerun()

    if st.button("Logout"):
        st.session_state.admin_logged_in = False
        st.session_state.admin_user = ""
        st.session_state.admin_password = ""
        st.rerun()

# ----------------------------------
# Volunteer Login Page
# ----------------------------------
def volunteer_login_page():
    st.title("🗳️ NSS Election System - Volunteer Login")
    roll = st.text_input("Enter Your Roll Number")
    if st.button("Login"):
        volunteer = get_volunteer_by_roll(roll)
        if volunteer:
            st.session_state.volunteer_logged_in = True
            st.session_state.volunteer_id = volunteer['id']
            st.session_state.volunteer_name = volunteer['name']
            st.success(f"Welcome {volunteer['name']}!")
            st.rerun()
        else:
            st.error("Volunteer not found. Please check your roll number.")

# ----------------------------------
# Voting Page
# ----------------------------------
def voting_page():
    st.title(f"🗳️ Vote Now, {st.session_state.volunteer_name}")

    positions = get_unique_positions()
    if not positions:
        st.warning("No positions found. Contact admin.")
        return

    votes = {}
    for pos in positions:
        # Fetch candidates for this position
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, roll_number FROM candidates WHERE position1=? OR position2=?", (pos, pos))
        candidates = c.fetchall()
        conn.close()

        options = {f"{cand['name']} ({cand['roll_number']})": cand['id'] for cand in candidates}
        choice = st.radio(f"Select candidate for position: {pos}", options.keys())
        votes[pos] = options[choice]

    if st.button("Submit Vote"):
        # Check if volunteer has voted for any position
        already_voted_positions = [pos for pos in positions if has_voted(st.session_state.volunteer_id, pos)]

        if already_voted_positions:
            st.error(f"You have already voted for position(s): {', '.join(already_voted_positions)}")
        else:
            # Submit votes
            for pos, candidate_id in votes.items():
                submit_vote(st.session_state.volunteer_id, candidate_id, pos)
            st.success("Thank you! Your votes have been submitted.")
            # Logout volunteer after voting
            st.session_state.volunteer_logged_in = False
            st.session_state.volunteer_id = None
            st.session_state.volunteer_name = ""
            st.rerun()

    if st.button("Logout"):
        st.session_state.volunteer_logged_in = False
        st.session_state.volunteer_id = None
        st.session_state.volunteer_name = ""
        st.rerun()

# ----------------------------------
# Main App Logic
# ----------------------------------
def main():
    st.sidebar.title("NSS Election System")

    if st.session_state.admin_logged_in:
        page = st.sidebar.selectbox("Admin Menu", ["Admin Panel", "Logout"])
        if page == "Admin Panel":
            admin_panel_page()
        elif page == "Logout":
            st.session_state.admin_logged_in = False
            st.session_state.admin_user = ""
            st.session_state.admin_password = ""
            st.rerun()

    elif st.session_state.volunteer_logged_in:
        page = st.sidebar.selectbox("Volunteer Menu", ["Vote", "Logout"])
        if page == "Vote":
            voting_page()
        elif page == "Logout":
            st.session_state.volunteer_logged_in = False
            st.session_state.volunteer_id = None
            st.session_state.volunteer_name = ""
            st.rerun()

    else:
        user_type = st.sidebar.selectbox("Login As", ["Admin", "Volunteer"])
        if user_type == "Admin":
            admin_login_page()
        else:
            volunteer_login_page()

# ----------------------------------
# Run setup and app
# ----------------------------------
if __name__ == "__main__":
    init_session_state()
    create_tables()
    create_admin()
    main()
