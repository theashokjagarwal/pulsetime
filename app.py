import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "attendance.db"
STATIC_DIR = APP_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

LATE_AFTER = "09:15:00"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Staff',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            status TEXT NOT NULL DEFAULT 'absent',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(employee_id, work_date),
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
        );
        """
    )
    count = db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    if count == 0:
        now = datetime.now().isoformat(timespec="seconds")
        employees = [
            ("EMP001", "Aisha Rahman", "aisha.rahman@company.com", "Engineering", "Software Engineer"),
            ("EMP002", "Daniel Chen", "daniel.chen@company.com", "Engineering", "QA Analyst"),
            ("EMP003", "Maria Lopez", "maria.lopez@company.com", "Human Resources", "HR Coordinator"),
            ("EMP004", "Omar Hassan", "omar.hassan@company.com", "Finance", "Accountant"),
            ("EMP005", "Priya Patel", "priya.patel@company.com", "Operations", "Office Manager"),
            ("EMP006", "James Okonkwo", "james.okonkwo@company.com", "Sales", "Account Executive"),
        ]
        db.executemany(
            """
            INSERT INTO employees (code, name, email, department, role, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            [(*row, now) for row in employees],
        )
        rows = db.execute("SELECT id, code FROM employees ORDER BY id").fetchall()
        id_by_code = {row[1]: row[0] for row in rows}
        today = date.today()
        samples = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            work_date = day.isoformat()
            records = [
                ("EMP001", "08:52:00", "17:05:00", "present"),
                ("EMP002", "09:28:00", "17:12:00", "late"),
                ("EMP003", "08:47:00", "16:58:00", "present"),
                ("EMP004", None, None, "absent"),
                ("EMP005", "09:02:00", "17:30:00", "present"),
                ("EMP006", "08:40:00", "18:10:00", "present"),
            ]
            if day == today:
                records = [
                    ("EMP001", "08:54:00", None, "present"),
                    ("EMP002", "09:31:00", None, "late"),
                    ("EMP003", None, None, "absent"),
                    ("EMP004", "08:59:00", None, "present"),
                    ("EMP005", None, None, "absent"),
                    ("EMP006", "08:41:00", None, "present"),
                ]
            for code, cin, cout, status in records:
                samples.append(
                    (id_by_code[code], work_date, cin, cout, status, now)
                )
        db.executemany(
            """
            INSERT INTO attendance (employee_id, work_date, check_in, check_out, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, '', ?)
            """,
            samples,
        )
    db.commit()
    db.close()


def row_to_dict(row):
    return dict(row) if row is not None else None


def today_str():
    return date.today().isoformat()


def now_time():
    return datetime.now().strftime("%H:%M:%S")


def classify_status(check_in):
    if not check_in:
        return "absent"
    return "late" if check_in > LATE_AFTER else "present"


def hours_between(check_in, check_out):
    if not check_in or not check_out:
        return None
    start = datetime.strptime(check_in, "%H:%M:%S")
    end = datetime.strptime(check_out, "%H:%M:%S")
    delta = (end - start).total_seconds()
    if delta < 0:
        return None
    return round(delta / 3600, 2)


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/dashboard")
def dashboard():
    db = get_db()
    work_date = request.args.get("date") or today_str()
    total = db.execute(
        "SELECT COUNT(*) FROM employees WHERE status = 'active'"
    ).fetchone()[0]
    stats = db.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS present,
            SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) AS late,
            SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) AS absent
        FROM attendance
        WHERE work_date = ?
        """,
        (work_date,),
    ).fetchone()
    present = stats["present"] or 0
    late = stats["late"] or 0
    marked = present + late + (stats["absent"] or 0)
    unmarked = max(total - marked, 0)
    absent = (stats["absent"] or 0) + unmarked
    recent = db.execute(
        """
        SELECT a.id, a.work_date, a.check_in, a.check_out, a.status,
               e.code, e.name, e.department
        FROM attendance a
        JOIN employees e ON e.id = a.employee_id
        ORDER BY a.work_date DESC, a.check_in DESC
        LIMIT 8
        """
    ).fetchall()
    departments = db.execute(
        """
        SELECT e.department,
               COUNT(*) AS total,
               SUM(CASE WHEN a.status IN ('present', 'late') THEN 1 ELSE 0 END) AS on_site
        FROM employees e
        LEFT JOIN attendance a
            ON a.employee_id = e.id AND a.work_date = ?
        WHERE e.status = 'active'
        GROUP BY e.department
        ORDER BY e.department
        """,
        (work_date,),
    ).fetchall()
    return jsonify(
        {
            "date": work_date,
            "total_employees": total,
            "present": present,
            "late": late,
            "absent": absent,
            "recent": [row_to_dict(r) for r in recent],
            "departments": [row_to_dict(r) for r in departments],
        }
    )


@app.get("/api/employees")
def list_employees():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    department = (request.args.get("department") or "").strip()
    sql = "SELECT * FROM employees WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR code LIKE ? OR email LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])
    if department:
        sql += " AND department = ?"
        params.append(department)
    sql += " ORDER BY name"
    rows = db.execute(sql, params).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/employees")
def create_employee():
    data = request.get_json(silent=True) or {}
    required = ["code", "name", "email", "department"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO employees (code, name, email, department, role, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                data["code"].strip().upper(),
                data["name"].strip(),
                data["email"].strip().lower(),
                data["department"].strip(),
                (data.get("role") or "Staff").strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Employee code or email already exists"}), 409
    row = db.execute("SELECT * FROM employees WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.put("/api/employees/<int:employee_id>")
def update_employee(employee_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    existing = db.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Employee not found"}), 404
    fields = {
        "code": (data.get("code") or existing["code"]).strip().upper(),
        "name": (data.get("name") or existing["name"]).strip(),
        "email": (data.get("email") or existing["email"]).strip().lower(),
        "department": (data.get("department") or existing["department"]).strip(),
        "role": (data.get("role") or existing["role"]).strip(),
        "status": (data.get("status") or existing["status"]).strip(),
    }
    try:
        db.execute(
            """
            UPDATE employees
            SET code = ?, name = ?, email = ?, department = ?, role = ?, status = ?
            WHERE id = ?
            """,
            (
                fields["code"],
                fields["name"],
                fields["email"],
                fields["department"],
                fields["role"],
                fields["status"],
                employee_id,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Employee code or email already exists"}), 409
    row = db.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.get("/api/attendance")
def list_attendance():
    db = get_db()
    work_date = request.args.get("date") or today_str()
    rows = db.execute(
        """
        SELECT e.id AS employee_id, e.code, e.name, e.department, e.role, e.status AS employee_status,
               a.id AS attendance_id, a.work_date, a.check_in, a.check_out, a.status, a.notes
        FROM employees e
        LEFT JOIN attendance a
            ON a.employee_id = e.id AND a.work_date = ?
        WHERE e.status = 'active'
        ORDER BY e.name
        """,
        (work_date,),
    ).fetchall()
    records = []
    for row in rows:
        item = row_to_dict(row)
        item["status"] = item["status"] or "absent"
        item["hours"] = hours_between(item["check_in"], item["check_out"])
        records.append(item)
    return jsonify({"date": work_date, "records": records})


@app.post("/api/attendance/check-in")
def check_in():
    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    if not employee_id:
        return jsonify({"error": "employee_id is required"}), 400
    db = get_db()
    employee = db.execute(
        "SELECT * FROM employees WHERE id = ? AND status = 'active'",
        (employee_id,),
    ).fetchone()
    if not employee:
        return jsonify({"error": "Active employee not found"}), 404
    work_date = data.get("date") or today_str()
    check_in_time = data.get("time") or now_time()
    if len(check_in_time) == 5:
        check_in_time += ":00"
    status = classify_status(check_in_time)
    existing = db.execute(
        "SELECT * FROM attendance WHERE employee_id = ? AND work_date = ?",
        (employee_id, work_date),
    ).fetchone()
    if existing and existing["check_in"]:
        return jsonify({"error": "Already checked in for this date"}), 409
    now = datetime.now().isoformat(timespec="seconds")
    if existing:
        db.execute(
            """
            UPDATE attendance
            SET check_in = ?, status = ?, notes = ?
            WHERE id = ?
            """,
            (check_in_time, status, data.get("notes") or "", existing["id"]),
        )
        record_id = existing["id"]
    else:
        cursor = db.execute(
            """
            INSERT INTO attendance (employee_id, work_date, check_in, check_out, status, notes, created_at)
            VALUES (?, ?, ?, NULL, ?, ?, ?)
            """,
            (employee_id, work_date, check_in_time, status, data.get("notes") or "", now),
        )
        record_id = cursor.lastrowid
    db.commit()
    row = db.execute("SELECT * FROM attendance WHERE id = ?", (record_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.post("/api/attendance/check-out")
def check_out():
    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    if not employee_id:
        return jsonify({"error": "employee_id is required"}), 400
    db = get_db()
    work_date = data.get("date") or today_str()
    existing = db.execute(
        "SELECT * FROM attendance WHERE employee_id = ? AND work_date = ?",
        (employee_id, work_date),
    ).fetchone()
    if not existing or not existing["check_in"]:
        return jsonify({"error": "Check-in required before check-out"}), 400
    if existing["check_out"]:
        return jsonify({"error": "Already checked out for this date"}), 409
    check_out_time = data.get("time") or now_time()
    if len(check_out_time) == 5:
        check_out_time += ":00"
    db.execute(
        "UPDATE attendance SET check_out = ? WHERE id = ?",
        (check_out_time, existing["id"]),
    )
    db.commit()
    row = db.execute("SELECT * FROM attendance WHERE id = ?", (existing["id"],)).fetchone()
    return jsonify(row_to_dict(row))


@app.post("/api/attendance/mark-absent")
def mark_absent():
    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    if not employee_id:
        return jsonify({"error": "employee_id is required"}), 400
    db = get_db()
    work_date = data.get("date") or today_str()
    existing = db.execute(
        "SELECT * FROM attendance WHERE employee_id = ? AND work_date = ?",
        (employee_id, work_date),
    ).fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    notes = data.get("notes") or "Marked absent"
    if existing:
        db.execute(
            """
            UPDATE attendance
            SET check_in = NULL, check_out = NULL, status = 'absent', notes = ?
            WHERE id = ?
            """,
            (notes, existing["id"]),
        )
        record_id = existing["id"]
    else:
        cursor = db.execute(
            """
            INSERT INTO attendance (employee_id, work_date, check_in, check_out, status, notes, created_at)
            VALUES (?, ?, NULL, NULL, 'absent', ?, ?)
            """,
            (employee_id, work_date, notes, now),
        )
        record_id = cursor.lastrowid
    db.commit()
    row = db.execute("SELECT * FROM attendance WHERE id = ?", (record_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.get("/api/reports")
def reports():
    db = get_db()
    end = request.args.get("to") or today_str()
    start = request.args.get("from") or (date.today() - timedelta(days=6)).isoformat()
    summary = db.execute(
        """
        SELECT e.id, e.code, e.name, e.department,
               COUNT(a.id) AS days_recorded,
               SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_days,
               SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) AS late_days,
               SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_days
        FROM employees e
        LEFT JOIN attendance a
            ON a.employee_id = e.id AND a.work_date BETWEEN ? AND ?
        WHERE e.status = 'active'
        GROUP BY e.id
        ORDER BY e.name
        """,
        (start, end),
    ).fetchall()
    daily = db.execute(
        """
        SELECT work_date,
               SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS present,
               SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) AS late,
               SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) AS absent
        FROM attendance
        WHERE work_date BETWEEN ? AND ?
        GROUP BY work_date
        ORDER BY work_date
        """,
        (start, end),
    ).fetchall()
    return jsonify(
        {
            "from": start,
            "to": end,
            "employees": [row_to_dict(r) for r in summary],
            "daily": [row_to_dict(r) for r in daily],
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
