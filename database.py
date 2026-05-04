import sqlite3
import os
import datetime

# -------------------------------
# PATH SETUP
# -------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")


# -------------------------------
# DATABASE SETUP
# -------------------------------
def create_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Students table
    c.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        roll TEXT,
        class TEXT,
        section TEXT,
        reg_no TEXT,
        created_at TEXT
    )
    """)

    # Attendance table
    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        name TEXT,
        timestamp TEXT
    )
    """)

    conn.commit()
    conn.close()


# -------------------------------
# ADD STUDENT
# -------------------------------
def add_student():
    print("\n--- Add Student ---")

    name = input("Enter student name: ").strip()
    roll = input("Enter roll number: ").strip()
    cls = input("Enter class: ").strip()
    section = input("Enter section: ").strip()
    reg_no = input("Enter registration number: ").strip()

    if not name:
        print("❌ Name is required")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    now = datetime.datetime.utcnow().isoformat()

    c.execute("""
    INSERT INTO students (name, roll, class, section, reg_no, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (name, roll, cls, section, reg_no, now))

    conn.commit()
    conn.close()

    print("✔ Student added successfully")


# -------------------------------
# MARK ATTENDANCE
# -------------------------------
def mark_attendance():
    print("\n--- Mark Attendance ---")

    student_id = input("Enter student ID: ").strip()

    if not student_id.isdigit():
        print("❌ Invalid student ID")
        return

    student_id = int(student_id)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get student name
    c.execute("SELECT name FROM students WHERE id=?", (student_id,))
    row = c.fetchone()

    if not row:
        print("❌ Student not found")
        conn.close()
        return

    name = row[0]
    today = datetime.datetime.utcnow().date().isoformat()

    # Check duplicate attendance
    c.execute("""
    SELECT id FROM attendance
    WHERE student_id=? AND DATE(timestamp)=?
    """, (student_id, today))

    if c.fetchone():
        print(f"⚠ Attendance already marked for today: {name}")
        conn.close()
        return

    ts = datetime.datetime.utcnow().isoformat()

    c.execute("""
    INSERT INTO attendance (student_id, name, timestamp)
    VALUES (?, ?, ?)
    """, (student_id, name, ts))

    conn.commit()
    conn.close()

    print(f"✔ Attendance marked for {name}")


# -------------------------------
# VIEW STUDENTS
# -------------------------------
def view_students():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id, name, class, section FROM students ORDER BY id ASC")
    rows = c.fetchall()

    conn.close()

    print("\n--- Student List ---")
    if not rows:
        print("No students found")
        return

    for r in rows:
        print(f"ID: {r[0]} | Name: {r[1]} | Class: {r[2]} | Section: {r[3]}")


# -------------------------------
# VIEW ATTENDANCE
# -------------------------------
def view_attendance():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT student_id, name, timestamp FROM attendance ORDER BY timestamp DESC")
    rows = c.fetchall()

    conn.close()

    print("\n--- Attendance Records ---")
    if not rows:
        print("No attendance records")
        return

    for r in rows:
        print(f"ID: {r[0]} | Name: {r[1]} | Time: {r[2]}")


# -------------------------------
# MENU SYSTEM
# -------------------------------
def menu():
    while True:
        print("\n====== ATTENDANCE SYSTEM ======")
        print("1. Add Student")
        print("2. View Students")
        print("3. Mark Attendance")
        print("4. View Attendance")
        print("5. Exit")

        choice = input("Enter choice: ").strip()

        if choice == "1":
            add_student()
        elif choice == "2":
            view_students()
        elif choice == "3":
            mark_attendance()
        elif choice == "4":
            view_attendance()
        elif choice == "5":
            print("Exiting...")
            break
        else:
            print("❌ Invalid choice")


# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    create_tables()
    menu()