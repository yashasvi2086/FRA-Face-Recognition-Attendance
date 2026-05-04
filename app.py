import os
import io
import threading
import sqlite3
import datetime
import json
from flask import Flask, render_template, request, jsonify, send_file

from model import (
    train_model_background,
    extract_embeddings_for_image,
    load_model_if_exists,
    predict_with_model
)

# -------------------------------
# PATHS
# -------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")
DATASET_DIR = os.path.join(APP_DIR, "dataset")
TRAIN_STATUS_FILE = os.path.join(APP_DIR, "train_status.json")

os.makedirs(DATASET_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")

# -------------------------------
# DATABASE
# -------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        name TEXT,
        timestamp TEXT
    )
    """)

    # Safe alter
    try:
        c.execute("ALTER TABLE attendance ADD COLUMN timestamp TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()

# -------------------------------
# TRAIN STATUS
# -------------------------------
def write_train_status(status):
    with open(TRAIN_STATUS_FILE, "w") as f:
        json.dump(status, f)

def read_train_status():
    if not os.path.exists(TRAIN_STATUS_FILE):
        return {"running": False, "progress": 0, "message": "Not trained"}
    with open(TRAIN_STATUS_FILE, "r") as f:
        return json.load(f)

write_train_status({"running": False, "progress": 0, "message": "No training yet"})

# -------------------------------
# ROUTES
# -------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "GET":
        return render_template("add_student.html")

    name = request.form.get("name", "").strip()
    roll = request.form.get("roll", "")
    cls = request.form.get("class", "")
    sec = request.form.get("sec", "")
    reg_no = request.form.get("reg_no", "")

    if not name:
        return jsonify({"error": "Name required"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    now = datetime.datetime.utcnow().isoformat()

    c.execute("""
    INSERT INTO students (name, roll, class, section, reg_no, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (name, roll, cls, sec, reg_no, now))

    student_id = c.lastrowid

    conn.commit()
    conn.close()

    os.makedirs(os.path.join(DATASET_DIR, str(student_id)), exist_ok=True)

    return jsonify({"student_id": student_id})

@app.route("/upload_face", methods=["POST"])
def upload_face():
    student_id = request.form.get("student_id")

    if not student_id:
        return jsonify({"error": "student_id required"}), 400

    files = request.files.getlist("images[]")
    folder = os.path.join(DATASET_DIR, student_id)
    os.makedirs(folder, exist_ok=True)

    for i, f in enumerate(files):
        f.save(os.path.join(folder, f"{i}.jpg"))

    return jsonify({"saved": len(files)})

@app.route("/train_model")
def train_model():
    status = read_train_status()

    if status["running"]:
        return jsonify({"status": "already_running"}), 202

    write_train_status({"running": True, "progress": 0, "message": "Starting training"})

    def progress_cb(p, m):
        write_train_status({"running": True, "progress": p, "message": m})

    threading.Thread(
        target=train_model_background,
        args=(DATASET_DIR, progress_cb),
        daemon=True
    ).start()

    return jsonify({"status": "started"}), 202

@app.route("/train_status")
def train_status():
    return jsonify(read_train_status())

@app.route("/mark_attendance")
def mark_attendance():
    return render_template("mark_attendance.html")

@app.route("/recognize_face", methods=["POST"])
def recognize_face():
    if "image" not in request.files:
        return jsonify({"recognized": False, "error": "no image"}), 400

    embs = extract_embeddings_for_image(request.files["image"].stream)

    if not embs:
        return jsonify({"recognized": False, "error": "no face detected"})

    clf = load_model_if_exists()
    if clf is None:
        return jsonify({"recognized": False, "error": "model not trained"})

    results = []

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    ts = datetime.datetime.utcnow().isoformat()
    today = datetime.datetime.utcnow().date().isoformat()

    for emb in embs:
        label, conf = predict_with_model(clf, emb)

        if label == "Unknown":
            results.append({
                "recognized": False,
                "error": f"Low confidence ({conf:.2f})"
            })
            continue

        c.execute("SELECT name FROM students WHERE id=?", (int(label),))
        row = c.fetchone()

        if not row:
            results.append({
                "recognized": False,
                "error": f"Obsolete ID: {label}"
            })
            continue

        name = row[0]

        c.execute("""
        SELECT * FROM attendance
        WHERE student_id=? AND DATE(timestamp)=?
        """, (int(label), today))

        if c.fetchone():
            results.append({
                "recognized": True,
                "name": name,
                "message": "Already marked"
            })
            continue

        c.execute("""
        INSERT INTO attendance (student_id, name, timestamp)
        VALUES (?, ?, ?)
        """, (int(label), name, ts))

        conn.commit()

        results.append({
            "recognized": True,
            "name": name,
            "message": "Marked present"
        })

    conn.close()

    return jsonify({
        "recognized": any(r.get("recognized") for r in results),
        "results": results
    })

@app.route("/attendance_record")
def attendance_record():
    period = request.args.get("period", "all")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = "SELECT * FROM attendance"

    if period == "daily":
        query += " WHERE DATE(timestamp) = DATE('now')"
    elif period == "weekly":
        query += " WHERE DATE(timestamp) >= DATE('now', '-7 days')"
    elif period == "monthly":
        query += " WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')"

    query += " ORDER BY timestamp DESC"

    c.execute(query)
    rows = c.fetchall()

    conn.close()

    return render_template("attendance_record.html", records=rows, period=period)

@app.route("/attendance_stats")
def attendance_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    SELECT DATE(timestamp), COUNT(*)
    FROM attendance
    GROUP BY DATE(timestamp)
    ORDER BY DATE(timestamp)
    """)

    rows = c.fetchall()
    conn.close()

    return jsonify({
        "dates": [r[0] for r in rows],
        "counts": [r[1] for r in rows]
    })

@app.route("/download_csv")
def download_csv():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT * FROM attendance")
    rows = c.fetchall()

    conn.close()

    output = io.StringIO()
    output.write("id,student_id,name,timestamp\n")

    for r in rows:
        output.write(f"{r[0]},{r[1]},{r[2]},{r[3]}\n")

    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    mem.seek(0)

    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="attendance.csv")

@app.route("/dashboard_stats")
def dashboard_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]

    today = datetime.datetime.utcnow().date().isoformat()
    c.execute("SELECT COUNT(*) FROM attendance WHERE DATE(timestamp)=?", (today,))
    attendance_today = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT class) FROM students")
    total_classes = c.fetchone()[0]

    c.execute("SELECT name, timestamp FROM attendance ORDER BY timestamp DESC LIMIT 5")
    recent = [{"name": r[0], "time": r[1]} for r in c.fetchall()]

    conn.close()

    return jsonify({
        "total_students": total_students,
        "attendance_today": attendance_today,
        "total_classes": total_classes,
        "recent_activity": recent
    })

@app.route("/students_list")
def students_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT * FROM students ORDER BY name ASC")
    rows = c.fetchall()

    conn.close()

    students = [{
        "id": r[0],
        "name": r[1],
        "roll": r[2],
        "class": r[3],
        "section": r[4],
        "reg_no": r[5]
    } for r in rows]

    return render_template("students.html", students=students)

@app.route("/delete_student/<int:id>", methods=["DELETE"])
def delete_student(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DELETE FROM students WHERE id=?", (id,))
    c.execute("DELETE FROM attendance WHERE student_id=?", (id,))

    conn.commit()
    conn.close()

    student_dir = os.path.join(DATASET_DIR, str(id))
    if os.path.exists(student_dir):
        import shutil
        shutil.rmtree(student_dir)

    return jsonify({"success": True})

@app.route("/student_image/<int:id>")
def student_image(id):
    image_path = os.path.join(DATASET_DIR, str(id), "0.jpg")

    if os.path.exists(image_path):
        return send_file(image_path, mimetype='image/jpeg')

    return "", 404

@app.route("/student/<int:id>")
def student_profile(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT * FROM students WHERE id=?", (id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return "Student not found", 404

    student = {
        "id": row[0],
        "name": row[1],
        "roll": row[2],
        "class": row[3],
        "section": row[4],
        "reg_no": row[5]
    }

    c.execute("SELECT COUNT(DISTINCT DATE(timestamp)) FROM attendance")
    total_days = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(DISTINCT DATE(timestamp)) FROM attendance WHERE student_id=?", (id,))
    present_days = c.fetchone()[0] or 0

    conn.close()

    absent_days = max(0, total_days - present_days)

    percentage = round((present_days / total_days) * 100, 1) if total_days > 0 else 0

    stats = {
        "total_days": total_days,
        "present_days": present_days,
        "absent_days": absent_days,
        "percentage": percentage
    }

    return render_template("student_profile.html", student=student, stats=stats)

@app.route("/edit_student/<int:id>", methods=["POST"])
def edit_student(id):
    name = request.form.get("name", "").strip()
    roll = request.form.get("roll", "")
    cls = request.form.get("class", "")
    sec = request.form.get("sec", "")
    reg_no = request.form.get("reg_no", "")

    if not name:
        return jsonify({"error": "Name required"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    UPDATE students
    SET name=?, roll=?, class=?, section=?, reg_no=?
    WHERE id=?
    """, (name, roll, cls, sec, reg_no, id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)