import streamlit as st 
import sqlite3
import hashlib
import os
import pandas as pd
from io import BytesIO

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
              
              CREATE TABLE IF NOT EXISTS votes(
                  student_id TEXT,
                  position TEXT,
                  candidate_id INTEGER,
                  PRIMARY KEY (student_id,position),
                  FOREIGN KEY (student_id) REFERENCES volunteers(student_id),
                  FOREIGN KEY (candidate_id) REFERENCES candidates(id)
              )
            ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS volunteers (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            year INTEGER NOT NULL,
            branch TEXT NOT NULL,
            phone TEXT NOT NULL,
            voted INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_number TEXT NOT NULL,
            year INTEGER NOT NULL,
            branch TEXT NOT NULL,
            phone TEXT NOT NULL,
            position1 TEXT NOT NULL,
            position2 TEXT,
            photo_path TEXT,
            votes INTEGER DEFAULT 0
        )
    ''')

    # Default admin credentials
    c.execute("SELECT * FROM admin WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admin (username, password) VALUES (?, ?)",
                  ('admin', hash_password('admin123')))
    conn.commit()
    conn.close()

init_db()

# ---------- Database Operations ----------
def add_volunteer(student_id, name, year, branch, phone):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO volunteers (student_id, name, year, branch, phone) VALUES (?, ?, ?, ?, ?)",
                  (student_id.lower().strip(), name.strip(), year, branch.strip(), phone.strip()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def delete_candidate(candidate_id):
    conn = get_db_connection()
    c = conn.cursor()
    # Optionally delete photo file as well
    c.execute("SELECT photo_path FROM candidates WHERE id = ?", (candidate_id,))
    photo_path = c.fetchone()
    if photo_path and photo_path[0]:
        try:
            os.remove(photo_path[0])
        except Exception:
            pass
    c.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
    conn.commit()
    conn.close()

def delete_volunteer(student_id):
    conn = get_db_connection()
    c = conn.cursor()
    # Remove volunteer and their votes
    c.execute("DELETE FROM votes WHERE student_id = ?", (student_id.lower().strip(),))
    c.execute("DELETE FROM volunteers WHERE student_id = ?", (student_id.lower().strip(),))
    conn.commit()
    conn.close()


def get_volunteers_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM volunteers", conn)
    conn.close()
    return df

def get_candidates_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, name, roll_number, year, branch, phone, position1, position2, votes FROM candidates", conn)
    conn.close()
    return df


def get_volunteer(student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT student_id, name, voted FROM volunteers WHERE student_id = ?",
              (student_id.lower().strip(),))
    vol = c.fetchone()
    conn.close()
    return vol

def vote_for_candidate(candidate_id, student_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE candidates SET votes = votes + 1 WHERE id = ?", (candidate_id,))
    c.execute("UPDATE volunteers SET voted = 1 WHERE student_id = ?",
              (student_id.lower().strip(),))
    conn.commit()
    conn.close()
    
def has_voted(student_id, position):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM votes WHERE student_id = ? AND position = ?", (student_id.lower().strip(), position))
    voted = c.fetchone() is not None
    conn.close()
    return voted

def vote_for_candidate(candidate_id, student_id, position):
    conn = get_db_connection()
    c = conn.cursor()
    # Check if already voted for this position
    c.execute("SELECT 1 FROM votes WHERE student_id = ? AND position = ?", (student_id.lower().strip(), position))
    if c.fetchone():
        conn.close()
        return False  # Already voted for this position

    # Record the vote
    c.execute("INSERT INTO votes (student_id, position, candidate_id) VALUES (?, ?, ?)", (student_id.lower().strip(), position, candidate_id))

    # Update candidate's vote count
    c.execute("UPDATE candidates SET votes = votes + 1 WHERE id = ?", (candidate_id,))
    conn.commit()
    conn.close()
    return True

def add_candidate(name, roll, year, branch, phone, pos1, pos2, photo):
    os.makedirs("photos", exist_ok=True)
    filename = f"photos/{roll.replace(' ', '_')}.png"
    with open(filename, "wb") as f:
        f.write(photo.getbuffer())
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO candidates (name, roll_number, year, branch, phone, position1, position2, photo_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name.strip(), roll.strip(), year, branch.strip(), phone.strip(), pos1.strip(), pos2.strip() if pos2 != "None" else None, filename))
    conn.commit()
    conn.close()

def get_candidates():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, photo_path, votes FROM candidates")
    candidates = c.fetchall()
    conn.close()
    return candidates

def check_admin_credentials(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM admin WHERE username = ? AND password = ?",
              (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_results_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT name, position1, position2, votes FROM candidates ORDER BY votes DESC", conn)
    conn.close()
    return df

def to_excel(df, sheet_name="Sheet1"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    processed_data = output.getvalue()
    return processed_data

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

branches = ["CSE", "CSE(DS)", "CSE(AI&ML)", "CIVIL", "MECH", "EEE", "ECE", "EIE"]
positions = ["President", "Vice President", "Secretary", "Event Co ordinator", "Treasurer",
             "Executive Member", "Digital Coordinator (Photography)", "Media Coordinator (Social Media, Poster)",
             "File Coordinator", "Joint Secretary", "Incharge of VIGNAN PRANADHARA"]

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
            st.info("✅ You have already voted. Thank you!")
        else:
            position = st.selectbox("Select Position", positions)
            if position:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT id, name, photo_path FROM candidates WHERE position1 = ?", (position,))
                candidates_for_pos = c.fetchall()
                conn.close()

                if not candidates_for_pos:
                    st.warning("No candidates available for this position.")
                else:
                    for cid, cname, photo_path in candidates_for_pos:
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.image(photo_path, width=80)
                        with col2:
                            if st.button(f"Vote for {cname}", key=f"vote_{cid}"):
                                if vote_for_candidate(cid, student_id, position):
                                    st.success(f"✅ Vote recorded for {cname} as {position}.")
                                    # Update voted state locally
                                    st.session_state['volunteer_info'] = (student_id, name, 1)
                                    st.experimental_rerun()
                                else:
                                    st.warning(f"❌ You have already voted for the position {position}.")


        if st.button("Logout"):
            st.session_state['volunteer_logged_in'] = False
            st.session_state['volunteer_info'] = None
            st.rerun()

elif menu == "Admin Login":
    st.header("🔐 Admin Login")

    if not st.session_state['admin_logged_in']:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password",key="password",autocomplete="off")
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
            vol_year = st.selectbox("Year", [1, 2, 3])
            vol_branch = st.selectbox("Branch", branches)
            vol_phone = st.text_input("Phone Number")
            if st.form_submit_button("Add Volunteer"):
                if vol_id and vol_name and vol_phone:
                    if add_volunteer(vol_id, vol_name, vol_year, vol_branch, vol_phone):
                        st.success("Volunteer added.")
                    else:
                        st.warning("Student ID already exists.")
                else:
                    st.warning("Please fill all fields.")

        st.markdown("---")

        st.subheader("➕ Add Candidate")
        with st.form("candidate_form"):
            cand_name = st.text_input("Candidate Name")
            roll = st.text_input("Roll Number")
            year = st.selectbox("Year", [1, 2, 3], key="c_year")
            branch = st.selectbox("Branch", branches, key="c_branch")
            phone = st.text_input("Phone Number", key="c_phone")
            pos1 = st.selectbox("Position 1", positions)
            pos2 = st.selectbox("Position 2 (Optional)", ["None"] + positions)
            photo = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
            if st.form_submit_button("Add Candidate"):
                if cand_name and photo:
                    add_candidate(cand_name, roll, year, branch, phone, pos1, pos2, photo)
                    st.success("Candidate added.")
                else:
                    st.warning("Fill both name and photo.")

        st.markdown("---")
        
        st.subheader("🗑️ Remove Candidate")
        candidates = get_candidates()
        if candidates:
            candidate_dict = {f"{name} ({branch})": cid for cid, name, _, _ in [(c[0], c[1], None, None) for c in candidates]}
            selected_cand = st.selectbox("Select Candidate to Remove", list(candidate_dict.keys()))
            if st.button("Remove Candidate"):
                delete_candidate(candidate_dict[selected_cand])
                st.success("Candidate removed.")
        else:
            st.info("No candidates available.")

        st.markdown("---")

        st.subheader("🗑️ Remove Volunteer")
        volunteers = get_volunteers_df()
        if not volunteers.empty:
            volunteer_list = volunteers['student_id'].tolist()
            selected_vol = st.selectbox("Select Volunteer to Remove", volunteer_list)
            if st.button("Remove Volunteer"):
                delete_volunteer(selected_vol)
                st.success("Volunteer removed.")
        else:
            st.info("No volunteers found.")
        
        st.subheader("📋 View Volunteers")
        volunteers_df = get_volunteers_df()
        st.dataframe(volunteers_df)

        st.download_button(label="Download Volunteers as Excel", data=to_excel(volunteers_df), file_name="volunteers.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        st.subheader("View Candidates")
        candidates_df=get_candidates_df()
        st.dataframe(candidates_df)
        
        st.download_button(label="Download Candidates as Exce", data=to_excel(candidates_df), file_name="candidates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


        st.subheader("📊 Election Results")
        df = get_results_df()
        st.dataframe(df)

        excel_data = to_excel(df)
        st.download_button("Download Results (Excel)", data=excel_data, file_name="results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        if st.button("Logout"):
            st.session_state['admin_logged_in'] = False
            st.rerun()
