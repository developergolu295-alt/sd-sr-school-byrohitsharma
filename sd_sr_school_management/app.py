import os, io, csv
from dotenv import load_dotenv
load_dotenv()
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from openpyxl import Workbook, load_workbook

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///school.db").replace("postgres://", "postgresql://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Change PORTAL_PASSWORD before putting this portal online.
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD", "@sd!kmpur")
ALLOWED_EXTENSIONS = {"xlsx"}

class Teacher(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="teacher")
    approved = db.Column(db.Boolean, default=True)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    school_class = db.relationship("SchoolClass", backref="teachers")

class SchoolClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    roll_no = db.Column(db.String(30), nullable=True)
    admission_no = db.Column(db.String(40), unique=True, nullable=True)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=False, index=True)
    guardian = db.Column(db.String(120), default="")
    phone = db.Column(db.String(30), default="")
    address = db.Column(db.Text, default="")
    school_class = db.relationship("SchoolClass", backref="students")

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(12), nullable=False)
    marked_by = db.Column(db.Integer, db.ForeignKey("teacher.id"))
    student = db.relationship("Student")
    __table_args__ = (db.UniqueConstraint("student_id", "day", name="unique_student_day"),)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    author = db.Column(db.String(120), default="")
    isbn = db.Column(db.String(40), default="")
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=False, index=True)
    total_copies = db.Column(db.Integer, default=1)
    available_copies = db.Column(db.Integer, default=1)
    school_class = db.relationship("SchoolClass", backref="books")

class BookIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    issued_on = db.Column(db.Date, default=date.today)
    returned_on = db.Column(db.Date, nullable=True)
    book = db.relationship("Book")
    student = db.relationship("Student")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Teacher, int(user_id))

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def can_access_class(class_id):
    return current_user.role == "admin" or current_user.class_id == class_id

@app.context_processor
def inject_globals():
    return {"lang": session.get("lang", "en"), "today": date.today().isoformat()}

@app.route("/")
def home():
    if not session.get("portal_unlocked"):
        return redirect(url_for("portal_lock"))
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/unlock", methods=["GET", "POST"])
def portal_lock():
    if request.method == "POST":
        if check_password_hash(app.config.get("PORTAL_PASSWORD_HASH", generate_password_hash(PORTAL_PASSWORD)), request.form.get("password", "")):
            session["portal_unlocked"] = True
            return redirect(url_for("login"))
        flash("Incorrect portal password.", "error")
    return render_template("unlock.html")

@app.route("/language/<code>")
def language(code):
    if code in ("en", "hi"):
        session["lang"] = code
    return redirect(request.referrer or url_for("home"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if not session.get("portal_unlocked"):
        return redirect(url_for("portal_lock"))
    classes = SchoolClass.query.order_by(SchoolClass.name).all()
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        if Teacher.query.filter_by(username=username).first():
            flash("That teacher ID is already in use.", "error")
        else:
            t = Teacher(name=request.form["name"].strip(), username=username,
                        password_hash=generate_password_hash(request.form["password"]),
                        class_id=int(request.form["class_id"]) if request.form.get("class_id") else None)
            db.session.add(t); db.session.commit()
            flash("Teacher account created. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", classes=classes)

@app.route("/login", methods=["GET", "POST"])
def login():
    if not session.get("portal_unlocked"):
        return redirect(url_for("portal_lock"))
    if request.method == "POST":
        t = Teacher.query.filter_by(username=request.form["username"].strip().lower()).first()
        if t and t.approved and check_password_hash(t.password_hash, request.form["password"]):
            login_user(t)
            return redirect(url_for("dashboard"))
        flash("Invalid teacher ID/password or account not approved.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        classes = SchoolClass.query.order_by(SchoolClass.name).all()
        students = Student.query.count()
        teachers = Teacher.query.count()
    else:
        classes = [current_user.school_class] if current_user.school_class else []
        students = Student.query.filter_by(class_id=current_user.class_id).count() if current_user.class_id else 0
        teachers = None
    return render_template("dashboard.html", classes=classes, student_count=students, teacher_count=teachers)

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", teachers=Teacher.query.order_by(Teacher.name).all(),
                           classes=SchoolClass.query.order_by(SchoolClass.name).all(),
                           students=Student.query.count())

@app.route("/admin/bootstrap", methods=["GET", "POST"])
def bootstrap():
    # First-run setup is only available after the portal is unlocked and while no accounts exist.
    if not session.get("portal_unlocked"):
        return redirect(url_for("portal_lock"))
    if Teacher.query.count() > 0:
        abort(404)
    if request.method == "POST":
        admin_user = Teacher(name=request.form["name"], username=request.form["username"].lower(),
            password_hash=generate_password_hash(request.form["password"]), role="admin")
        db.session.add(admin_user); db.session.commit()
        flash("Administrator created. Please sign in.", "success")
        return redirect(url_for("login"))
    return render_template("bootstrap.html")

@app.route("/classes/add", methods=["POST"])
@admin_required
def add_class():
    name = request.form["name"].strip()
    if name and not SchoolClass.query.filter_by(name=name).first():
        db.session.add(SchoolClass(name=name)); db.session.commit()
        flash("Class added.", "success")
    return redirect(url_for("admin"))

@app.route("/classes/<int:class_id>/password", methods=["POST"])
@login_required
def class_password(class_id):
    if not can_access_class(class_id): abort(403)
    c = db.session.get(SchoolClass, class_id)
    c.password_hash = generate_password_hash(request.form["password"])
    db.session.commit()
    flash("Class password updated securely.", "success")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/teachers/<int:teacher_id>/approve", methods=["POST"])
@admin_required
def approve_teacher(teacher_id):
    t = db.session.get(Teacher, teacher_id); t.approved = not t.approved
    db.session.commit()
    return redirect(url_for("admin"))

@app.route("/students/<int:class_id>", methods=["GET", "POST"])
@login_required
def students(class_id):
    if not can_access_class(class_id): abort(403)
    c = db.session.get(SchoolClass, class_id)
    if not c: abort(404)
    if request.method == "POST":
        s = Student(name=request.form["name"].strip(), roll_no=request.form.get("roll_no",""),
            admission_no=request.form.get("admission_no") or None, class_id=class_id,
            guardian=request.form.get("guardian",""), phone=request.form.get("phone",""),
            address=request.form.get("address",""))
        db.session.add(s); db.session.commit()
        flash("Student added.", "success")
        return redirect(url_for("students", class_id=class_id))
    order = request.args.get("order", "roll")
    query = Student.query.filter_by(class_id=class_id)
    records = query.order_by(func.lower(Student.name) if order == "alpha" else Student.roll_no, Student.name).all()
    return render_template("students.html", school_class=c, students=records, order=order)

@app.route("/students/<int:student_id>/print")
@login_required
def print_student(student_id):
    s = db.session.get(Student, student_id)
    if not s or not can_access_class(s.class_id): abort(403)
    return render_template("print_student.html", student=s)

@app.route("/attendance/<int:class_id>", methods=["GET", "POST"])
@login_required
def attendance(class_id):
    if not can_access_class(class_id): abort(403)
    c = db.session.get(SchoolClass, class_id)
    day = date.fromisoformat(request.values.get("day", date.today().isoformat()))
    roster = Student.query.filter_by(class_id=class_id).order_by(Student.roll_no, Student.name).all()
    if request.method == "POST":
        for s in roster:
            status = request.form.get(f"student_{s.id}", "Absent")
            row = Attendance.query.filter_by(student_id=s.id, day=day).first()
            if row:
                row.status = status; row.marked_by = current_user.id
            else:
                db.session.add(Attendance(student_id=s.id, day=day, status=status, marked_by=current_user.id))
        db.session.commit(); flash("Attendance saved.", "success")
        return redirect(url_for("attendance", class_id=class_id, day=day.isoformat()))
    existing = {a.student_id:a.status for a in Attendance.query.join(Student).filter(Student.class_id==class_id, Attendance.day==day).all()}
    return render_template("attendance.html", school_class=c, roster=roster, day=day, existing=existing)

@app.route("/library/<int:class_id>", methods=["GET", "POST"])
@login_required
def library(class_id):
    if not can_access_class(class_id): abort(403)
    c = db.session.get(SchoolClass, class_id)
    if request.method == "POST":
        b = Book(title=request.form["title"], author=request.form.get("author",""), isbn=request.form.get("isbn",""),
                 class_id=class_id, total_copies=max(1,int(request.form.get("copies",1))),
                 available_copies=max(1,int(request.form.get("copies",1))))
        db.session.add(b); db.session.commit()
        return redirect(url_for("library", class_id=class_id))
    books = Book.query.filter_by(class_id=class_id).order_by(Book.title).all()
    issues = BookIssue.query.join(Book).filter(Book.class_id==class_id, BookIssue.returned_on.is_(None)).all()
    roster = Student.query.filter_by(class_id=class_id).order_by(Student.name).all()
    return render_template("library.html", school_class=c, books=books, issues=issues, roster=roster)

@app.route("/library/issue", methods=["POST"])
@login_required
def issue_book():
    book = db.session.get(Book, int(request.form["book_id"]))
    student = db.session.get(Student, int(request.form["student_id"]))
    if not book or not student or book.class_id != student.class_id or not can_access_class(book.class_id): abort(403)
    if book.available_copies < 1:
        flash("No copies currently available.", "error")
    else:
        db.session.add(BookIssue(book_id=book.id, student_id=student.id))
        book.available_copies -= 1; db.session.commit(); flash("Book issued.", "success")
    return redirect(url_for("library", class_id=book.class_id))

@app.route("/library/return/<int:issue_id>", methods=["POST"])
@login_required
def return_book(issue_id):
    issue = db.session.get(BookIssue, issue_id)
    if not issue or not can_access_class(issue.book.class_id): abort(403)
    if not issue.returned_on:
        issue.returned_on = date.today(); issue.book.available_copies += 1; db.session.commit()
    return redirect(url_for("library", class_id=issue.book.class_id))

@app.route("/export/<int:class_id>")
@login_required
def export_students(class_id):
    if not can_access_class(class_id): abort(403)
    c = db.session.get(SchoolClass, class_id)
    wb = Workbook(); ws = wb.active; ws.title = "Students"
    ws.append(["Name","Roll No","Admission No","Class","Guardian","Phone","Address"])
    for s in Student.query.filter_by(class_id=class_id).order_by(Student.name).all():
        ws.append([s.name,s.roll_no,s.admission_no,c.name,s.guardian,s.phone,s.address])
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return send_file(out, as_attachment=True, download_name=f"{secure_filename(c.name)}_students.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/import/<int:class_id>", methods=["POST"])
@login_required
def import_students(class_id):
    if not can_access_class(class_id): abort(403)
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".xlsx"):
        flash("Upload an .xlsx file.", "error"); return redirect(url_for("students", class_id=class_id))
    wb = load_workbook(f, read_only=True, data_only=True); ws = wb.active
    # Required header names: Name, Roll No, Admission No, Guardian, Phone, Address
    headers = [str(v or "").strip().lower() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    idx = {h:i for i,h in enumerate(headers)}
    if "name" not in idx:
        flash("Excel must contain a 'Name' column.", "error")
        return redirect(url_for("students", class_id=class_id))
    added = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        def val(key):
            return str(row[idx[key]] or "").strip() if key in idx and idx[key] < len(row) else ""
        name = val("name")
        if not name: continue
        admission = val("admission no") or None
        if admission and Student.query.filter_by(admission_no=admission).first(): continue
        db.session.add(Student(name=name, roll_no=val("roll no"), admission_no=admission,
            class_id=class_id, guardian=val("guardian"), phone=val("phone"), address=val("address")))
        added += 1
    db.session.commit(); flash(f"Imported {added} student(s).", "success")
    return redirect(url_for("students", class_id=class_id))

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
