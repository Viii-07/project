from flask import Flask, request, jsonify, render_template, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from sqlalchemy import Enum, text  # Added missing import
import csv
from io import BytesIO, StringIO

# ---------------- CONFIG ---------------- #
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:Vinay*11@localhost/attendance_db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "supersecret"
app.config["JWT_SECRET_KEY"] = "jwtsecret"

db = SQLAlchemy(app)
jwt = JWTManager(app)

# ---------------- MODELS ---------------- #
class Teacher(db.Model):
    __tablename__ = "teachers"
    teacher_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.Enum("Teacher", "Admin", name="role_enum"), nullable=False)

class Student(db.Model):
    __tablename__ = "students"
    student_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    roll_no = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(5), nullable=False)

class Class(db.Model):
    __tablename__ = "classes"
    class_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(5), nullable=False)
    assigned_teacher_id = db.Column(db.String(50), db.ForeignKey("teachers.teacher_id"))

class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"
    attendance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.student_id"))
    class_id = db.Column(db.Integer, db.ForeignKey("classes.class_id"))
    teacher_id = db.Column(db.String(50), db.ForeignKey("teachers.teacher_id"))
    date = db.Column(db.Date, default=date.today)
    period_no = db.Column(db.Integer)
    status = db.Column(db.Enum("Present", "Absent", name="status_enum"))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    attempt_no = db.Column(db.Integer, default=1)
    is_final = db.Column(db.Boolean, default=True)

# ---------------- HELPERS ---------------- #
def hash_password(pw):
    return generate_password_hash(pw)

def verify_password(hash, pw):
    return check_password_hash(hash, pw)

def attendance_locked(teacher_id, class_id, dt, period_no):
    first = AttendanceRecord.query.filter_by(
        teacher_id=teacher_id, class_id=class_id,
        date=dt, period_no=period_no, attempt_no=1
    ).first()
    if not first:
        return False, None
    until = first.submitted_at + timedelta(minutes=10)
    return datetime.utcnow() < until, until

def admin_required():
    identity = get_jwt_identity()
    return identity and identity.get("role") == "Admin"

# ---------------- ROUTES ---------------- #
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    tid, pw, role = data.get("teacherId"), data.get("password"), data.get("role")
    user = Teacher.query.filter_by(teacher_id=tid, role=role).first()
    if not user or not verify_password(user.password, pw):
        return jsonify({"msg": "Invalid credentials"}), 401
    token = create_access_token(
        identity={"id": user.teacher_id, "role": user.role},
        expires_delta=timedelta(hours=8)
    )
    return jsonify({
        "access_token": token,
        "user":
          {"id": user.teacher_id, "name": user.name, "role": user.role}
    })

@app.route("/api/dashboard/<teacher_id>")
@jwt_required()
def dashboard(teacher_id):
    periods = [{"period_no": i, "is_free": (i % 3 == 0)} for i in range(1, 8)]
    return jsonify({"teacher_id": teacher_id, "date": date.today().isoformat(), "periods": periods})

@app.route("/api/attendance/submit", methods=["POST"])
@jwt_required()
def submit_attendance():
    data = request.get_json()
    teacher_id, class_id, period_no = data["teacher_id"], data["class_id"], data["period_no"]
    dt = date.fromisoformat(data.get("date", date.today().isoformat()))
    students = data["students"]

    locked, until = attendance_locked(teacher_id, class_id, dt, period_no)
    if locked:
        until_str = until.isoformat() if until else "unknown"
        return jsonify({"msg": "Locked until " + until_str}), 423

    original = AttendanceRecord.query.filter_by(
        teacher_id=teacher_id, class_id=class_id,
        date=dt, period_no=period_no, attempt_no=1
    ).first()
    attempt = 1 if not original else 2
    if attempt == 2 and AttendanceRecord.query.filter_by(
        teacher_id=teacher_id, class_id=class_id,
        date=dt, period_no=period_no, attempt_no=2
    ).first():
        return jsonify({"msg": "Reattempt already used"}), 403

    now = datetime.utcnow()
    for s in students:
        rec = AttendanceRecord()
        rec.student_id = s["student_id"]
        rec.class_id = class_id
        rec.teacher_id = teacher_id
        rec.date = dt
        rec.period_no = period_no
        rec.status = s["status"]
        rec.submitted_at = now
        rec.attempt_no = attempt
        db.session.add(rec)
    db.session.commit()

    return jsonify({"msg": "Attendance saved", "attempt_no": attempt})

@app.route("/api/students/<int:year>/<dept>/<section>")
@jwt_required()
def students(year, dept, section):
    rows = Student.query.filter_by(year=year, department=dept, section=section).all()
    return jsonify([{"id": s.student_id, "roll_no": s.roll_no, "name": s.name} for s in rows])

@app.route("/api/students", methods=["POST"])
@jwt_required()
def add_student():
    d = request.get_json()
    s = Student()
    s.roll_no = d["roll_no"]
    s.name = d["name"]
    s.year = d["year"]
    s.department = d["department"]
    s.section = d["section"]
    db.session.add(s)
    db.session.commit()
    return jsonify({"msg": "added", "id": s.student_id}), 201

@app.route("/api/students/<int:id>", methods=["PUT"])
@jwt_required()
def edit_student(id):
    d = request.get_json()
    s = Student.query.get_or_404(id)
    s.name = d.get("name", s.name)
    db.session.commit()
    return jsonify({"msg": "updated"})

@app.route("/api/students/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_student(id):
    s = Student.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return jsonify({"msg": "deleted"})

@app.route('/api/teachers')
def get_teachers():
    teachers = Teacher.query.all()
    return jsonify([
        {'teacher_id': t.teacher_id, 'name': t.name, 'department': t.department, 'email': t.email, 'role': t.role}
        for t in teachers
    ])

@app.route('/api/db-test')
def db_test():
    try:
        teachers = Teacher.query.all()
        return jsonify({
            'success': True,
            'count': len(teachers),
            'teachers': [t.teacher_id for t in teachers]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ---------------- ADMIN ROUTES ---------------- #
@app.route("/api/admin/attendance/<string:dt>/summary")
@jwt_required()
def admin_attendance_summary(dt):
    if not admin_required():
        return jsonify({"msg": "Admins only"}), 403
    d = date.fromisoformat(dt)
    rows = db.session.execute(
        text("""
        SELECT class_id,
            SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent
        FROM attendance_records
        WHERE date=:d
        GROUP BY class_id
        """),
        {"d": d}
    )
    return jsonify([dict(r) for r in rows])

@app.route("/api/admin/attendance/<int:class_id>/<string:dt>/details")
@jwt_required()
def admin_attendance_details(class_id, dt):
    if not admin_required():
        return jsonify({"msg": "Admins only"}), 403
    d = date.fromisoformat(dt)
    recs = AttendanceRecord.query.filter_by(class_id=class_id, date=d).all()
    out = []
    for r in recs:
        out.append({
            "student_id": r.student_id,
            "status": r.status,
            "period": r.period_no,
            "attempt": r.attempt_no,
            "submitted_at": r.submitted_at.isoformat(),
            "teacher_id": r.teacher_id
        })
    return jsonify(out)

@app.route('/api/admin/attendance/<int:class_id>/<string:dt>/download')
@jwt_required()
def download_attendance_report(class_id, dt):
    if not admin_required():
        return jsonify({'msg': 'Admins only'}), 403
    d = date.fromisoformat(dt)
    recs = AttendanceRecord.query.filter_by(class_id=class_id, date=d).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Roll No', 'Student Name', 'Status', 'Period', 'Attempt', 'Submitted At', 'Teacher ID'])
    for r in recs:
        student = Student.query.get(r.student_id)
        writer.writerow([
            student.roll_no if student else '',
            student.name if student else '',
            r.status,
            r.period_no,
            r.attempt_no,
            r.submitted_at,
            r.teacher_id
        ])
    mem = BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'attendance_report_{class_id}_{dt}.csv'
    )

@app.route("/index")
def index():
    return render_template("index.html")

@app.route("/admin-dashboard")
def admin_dashboard():
    return render_template("admin-dashboard.html")

@app.route("/attendance-form")
def attendance_form():
    return render_template("attendance-form.html")

@app.route("/attendance")
def attendance():
    return render_template("attendance.html")

@app.route("/teacher-dashboard")
def teacher_dashboard():
    return render_template("teacher-dashboard.html")

@app.route("/student-management")
def student_management():
    return render_template("student-management.html")

# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    app.run(debug=True)
