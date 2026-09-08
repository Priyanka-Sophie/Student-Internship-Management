import os
import uuid
from functools import wraps
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash
from models import Application, db, Internship, InternshipSource, Student, StudentSkill, User
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from resume_tools import extract_skills, match_score, split_skills
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'internship.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SIMS_SECRET_KEY", "change-this-sims-development-secret")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "resumes")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf"}

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )
SKILL_KEYWORDS = [
    "Python", "SQL", "Java", "JavaScript", "HTML", "CSS",
    "Git", "Excel", "Power BI", "Flutter", "React",
    "C++", "C#", "Machine Learning", "AWS", "Linux"
]

def extract_resume_skills(pdf_path):
    reader = PdfReader(pdf_path)
    resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return extract_skills(resume_text)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "error"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def ensure_database_schema():
    """Keep the existing local SQLite database compatible during development."""
    db.create_all()

    # Add student_id to users table if missing
    user_columns = {column["name"] for column in inspect(db.engine).get_columns("users")}
    schema_changed = False
    if "student_id" not in user_columns:
        db.session.execute(text("ALTER TABLE users ADD COLUMN student_id VARCHAR(50)"))
        schema_changed = True

    # Add resume_path to students table if missing
    student_columns = {column["name"] for column in inspect(db.engine).get_columns("students")}
    if "resume_path" not in student_columns:
        db.session.execute(text("ALTER TABLE students ADD COLUMN resume_path VARCHAR(255)"))
        schema_changed = True
    if "specialization" not in student_columns:
        db.session.execute(text("ALTER TABLE students ADD COLUMN specialization VARCHAR(100)"))
        schema_changed = True

    # Create student_skills table if it doesn't exist
    existing_tables = inspect(db.engine).get_table_names()
    if "student_skills" not in existing_tables:
        StudentSkill.__table__.create(db.engine)
    internship_columns = {column["name"] for column in inspect(db.engine).get_columns("internships")}
    for column_name, column_type in {
        "required_skills": "TEXT",
        "application_url": "VARCHAR(500)",
        "source_name": "VARCHAR(100)",
        "source_url": "VARCHAR(500)",
        "imported_at": "DATETIME",
        "external_id": "VARCHAR(150)",
        "status": "VARCHAR(20) DEFAULT 'pending'",
        "admin_approved": "BOOLEAN DEFAULT 0",
    }.items():
        if column_name not in internship_columns:
            db.session.execute(text(f"ALTER TABLE internships ADD COLUMN {column_name} {column_type}"))
            schema_changed = True
    if schema_changed:
        db.session.commit()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Administrator access is required.", "error")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def current_student():
    student = Student.query.filter_by(user_id=current_user.id).first()

    if student is None:
        student = Student(user_id=current_user.id)
        db.session.add(student)
        db.session.commit()

    return student


def academic_profile_complete(student):
    return bool(student and student.qualification and student.specialization and student.year)


def profile_completion(student):
    """Account (20%) plus academic details and resume (20% each)."""
    if not student:
        return 0
    completed = 1
    completed += bool(student.qualification)
    completed += bool(student.specialization)
    completed += bool(student.year)
    completed += bool(student.resume_path)
    return completed * 20


def get_recommendations(student):
    skills = [row.skill for row in StudentSkill.query.filter_by(student_id=student.id).all()]
    results = []
    for internship in Internship.query.filter_by(is_active=True, status="active", admin_approved=True).all():
        required_skills = split_skills(internship.required_skills)
        matched_topics = []
        score = match_score(skills, required_skills)
        match_type = "Employer-stated skill match"
        if not required_skills and internship.source_name and internship.source_name.startswith("OpenIntern"):
            topic_words = f"{internship.title} {internship.category}".casefold()
            groups = {
                "software": {"python", "java", "javascript", "html", "css", "git", "react", "c++", "c#", "flutter"},
                "data": {"python", "sql", "excel", "power bi", "tableau", "pandas", "numpy"},
                "design": {"figma", "css", "html"},
            }
            if any(term in topic_words for term in ("data", "analytics", "machine learning")):
                selected_group = "data"
            elif any(term in topic_words for term in ("ui", "ux", "frontend", "web design", "product design")):
                selected_group = "design"
            elif any(term in topic_words for term in ("software", "developer", "web development")):
                selected_group = "software"
            else:
                selected_group = None
            if selected_group:
                matched_topics = [skill for skill in skills if skill.casefold() in groups[selected_group]]
                if matched_topics:
                    score = round((len(matched_topics) / len(groups[selected_group])) * 100)
                    score = max(score, 35)
                    match_type = "Resume relevance to the live role"
        if score:
            matched = [skill for skill in skills if skill.casefold() in {item.casefold() for item in required_skills}]
            if not matched:
                matched = matched_topics
            results.append({"internship": internship, "score": score, "matched_skills": matched, "match_type": match_type})
    return sorted(results, key=lambda item: item["score"], reverse=True)

@app.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            (User.email == identifier.lower()) | (User.student_id == identifier.upper())
        ).first()

        if user and user.role == "student" and check_password_hash(user.password_hash, password):
            login_user(user, remember=request.form.get("remember") == "on")
            return redirect(url_for("dashboard"))

        flash("Incorrect email/student ID or password.", "error")
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        import re

        name = request.form.get("full_name", "").strip()
        student_id = request.form.get("student_id", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name:
            flash("Please enter your full name.", "error")

        elif not re.fullmatch(r"[A-Za-z ]{2,50}", name):
            flash("Full name must contain only letters and spaces.", "error")

        elif not student_id:
            flash("Please enter your Student ID.", "error")

        elif not re.fullmatch(r"[A-Za-z0-9._%+-]+@gmail\.com", email):
            flash("Please enter a valid Gmail address ending with @gmail.com.", "error")

        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")

        elif not re.search(r"[A-Z]", password):
            flash("Password must contain at least one uppercase letter.", "error")

        elif not re.search(r"[a-z]", password):
            flash("Password must contain at least one lowercase letter.", "error")

        elif not re.search(r"\d", password):
            flash("Password must contain at least one number.", "error")

        elif password != confirm_password:
            flash("The two passwords do not match.", "error")

        elif User.query.filter(
            (User.email == email) |
            (User.student_id == student_id)
        ).first():
            flash("An account already exists with that email or student ID.", "error")

        elif request.form.get("terms") != "on":
            flash("Please accept the Terms & Conditions to create an account.", "error")

        else:
            user = User(
                name=name,
                student_id=student_id,
                email=email,
                password_hash=generate_password_hash(password),
                role="student",
            )

            db.session.add(user)
            db.session.flush()

            db.session.add(Student(user_id=user.id))

            db.session.commit()

            flash("Account created. Please sign in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/dashboard")
@login_required
def dashboard():
    student = current_student()
    recommendations = get_recommendations(student)
    active_count = Internship.query.filter_by(is_active=True, status="active", admin_approved=True).count()
    return render_template(
        "student_dashboard_db.html",
        student=student,
        recommendations=recommendations[:3],
        active_count=active_count,
        applications_count=Application.query.filter_by(student_id=student.id).count(),
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    student = current_student()
    if request.method == "POST":
        student.qualification = request.form.get("qualification", "").strip()
        student.specialization = request.form.get("specialization", "").strip()
        student.year = request.form.get("year", "").strip()
        if not academic_profile_complete(student):
            flash("Please complete qualification, specialisation, and current year.", "error")
        else:
            db.session.commit()
            flash("Academic details saved. You can now upload your resume.", "success")
            return redirect(url_for("resume"))
    skills = StudentSkill.query.filter_by(student_id=student.id).order_by(StudentSkill.skill).all()
    return render_template("profile.html", student=student, skills=skills, academic_complete=academic_profile_complete(student), profile_percent=profile_completion(student))


@app.route("/resume")
@login_required
def resume():
    student = current_student()
    if not academic_profile_complete(student):
        flash("Complete your personal and academic details before uploading a resume.", "error")
        return redirect(url_for("profile"))
    skills = StudentSkill.query.filter_by(student_id=student.id).order_by(StudentSkill.skill).all()
    return render_template("resume.html", student=student, skills=skills)



@app.route("/upload-resume", methods=["POST"])
@login_required
def upload_resume():
    if not academic_profile_complete(current_student()):
        flash("Complete your personal and academic details before uploading a resume.", "error")
        return redirect(url_for("profile"))
    if "resume" not in request.files:
        flash("No file selected.", "error")
        return redirect(request.referrer or url_for("resume"))

    file = request.files["resume"]

    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(request.referrer or url_for("resume"))

    if file and allowed_file(file.filename):
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

        filename = f"student_{current_user.id}_{uuid.uuid4().hex}.pdf"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        file.save(filepath)

        student = Student.query.filter_by(user_id=current_user.id).first()

        if student:
            student.resume_path = os.path.join("uploads", "resumes", filename)

            # Remove old detected skills
            StudentSkill.query.filter_by(student_id=student.id).delete()

            try:
                skills = extract_resume_skills(filepath)
            except Exception:
                os.remove(filepath)
                flash("We could not read that PDF. Please upload a normal text-based resume PDF.", "error")
                return redirect(url_for("resume"))

            # Save detected skills
            for skill in skills:
                db.session.add(
                    StudentSkill(
                        student_id=student.id,
                        skill=skill,
                    )
                )

            db.session.commit()

        flash(f"Resume uploaded. SIMS found {len(skills)} skill(s).", "success")
        return redirect(url_for("resume"))

    flash("Only PDF resumes are allowed.", "error")
    return redirect(request.referrer or url_for("resume"))

@app.route("/internships/<slug>")
@login_required
def internship_detail(slug):
    internship = Internship.query.filter_by(slug=slug, is_active=True, status="active", admin_approved=True).first()

    if internship is None:
        abort(404)

    student = current_student()
    application = Application.query.filter_by(student_id=student.id, internship_id=internship.id).first()
    return render_template("internship_detail_db.html", internship=internship, required_skills=split_skills(internship.required_skills), application=application)


@app.post("/internships/<slug>/mark-applied")
@login_required
def mark_applied(slug):
    internship = Internship.query.filter_by(slug=slug, is_active=True, status="active", admin_approved=True).first_or_404()
    student = current_student()
    if not Application.query.filter_by(student_id=student.id, internship_id=internship.id).first():
        db.session.add(Application(student_id=student.id, internship_id=internship.id, status="Submitted"))
        db.session.commit()
        flash("Application saved in My Applications. Confirm progress with the employer directly.", "success")
    return redirect(url_for("applications"))


@app.route("/recommendations")
@login_required
def recommendations():
    student = current_student()
    query = request.args.get("q", "").strip().casefold()
    recommendations = get_recommendations(student)
    if query:
        recommendations = [item for item in recommendations if query in f"{item['internship'].title} {item['internship'].company} {item['internship'].category}".casefold()]
    return render_template("recommendations_search.html", recommendations=recommendations, query=query)


@app.route("/applications")
@login_required
def applications():
    student = current_student()
    applications = Application.query.filter_by(student_id=student.id).order_by(Application.applied_at.desc()).all()
    internship_ids = [item.internship_id for item in applications]
    internships_by_id = {item.id: item for item in Internship.query.filter(Internship.id.in_(internship_ids)).all()} if internship_ids else {}
    return render_template("applications_db.html", applications=applications, internships_by_id=internships_by_id)


@app.post("/applications/<int:application_id>/remove")
@login_required
def remove_application(application_id):
    student = current_student()
    application = Application.query.filter_by(id=application_id, student_id=student.id).first_or_404()
    db.session.delete(application)
    db.session.commit()
    flash("Removed from your SIMS application tracker. Your employer-site application is unchanged.", "success")
    return redirect(url_for("applications"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated and current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, role="admin").first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=request.form.get("remember") == "on")
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect administrator email or password.", "error")
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template(
        "admin_dashboard_db.html",
        students=Student.query.count(),
        total=Internship.query.count(),
        pending=Internship.query.filter_by(status="pending").count(),
        active=Internship.query.filter_by(status="active", admin_approved=True, is_active=True).count(),
        rejected=Internship.query.filter_by(status="rejected").count(),
        applications=Application.query.count(),
        recent_pending=Internship.query.filter_by(status="pending").order_by(Internship.imported_at.desc()).limit(5).all(),
    )


@app.route("/admin/internships")
@admin_required
def manage_internships():
    status = request.args.get("status", "all")
    query = Internship.query.order_by(Internship.imported_at.desc())
    if status != "all":
        query = query.filter_by(status=status)
    return render_template("manage_internships_review.html", internships=query.all(), selected_status=status)


@app.post("/admin/internships/<int:internship_id>/status")
@admin_required
def update_internship_status(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    status = request.form.get("status")
    if status not in {"active", "pending", "rejected", "expired"}:
        abort(400)
    internship.status = status
    internship.admin_approved = status == "active"
    internship.is_active = status == "active"
    db.session.commit()
    flash(f"{internship.title} is now {status.title()}.", "success")
    return redirect(url_for("manage_internships", status=request.form.get("return_status", "all")))


@app.post("/admin/sources/openintern/sync")
@admin_required
def sync_openintern():
    from live_internships import sync_live_internships
    try:
        count = sync_live_internships()
        flash(f"Fetched {count} live listings for admin review.", "success")
    except Exception:
        flash("The live source could not be reached. Please try again later.", "error")
    return redirect(url_for("manage_internships", status="pending"))


@app.route("/admin/sources")
@admin_required
def admin_sources():
    return render_template("admin_sources_db.html", sources=InternshipSource.query.order_by(InternshipSource.name).all())


@app.route("/internships")
@login_required
def internships():
    internships = Internship.query.filter_by(is_active=True, status="active", admin_approved=True).all()
    query = request.args.get("q", "").strip().casefold()
    if query:
        internships = [item for item in internships if query in f"{item.title} {item.company} {item.category} {item.location}".casefold()]
    return render_template("internships.html", internships=internships, query=query, profile_percent=profile_completion(current_student()))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/admin/students")
@admin_required
def manage_students():
    students = Student.query.order_by(Student.id.desc()).all()
    skills_by_student = {student.id: StudentSkill.query.filter_by(student_id=student.id).count() for student in students}
    users_by_id = {user.id: user for user in User.query.filter_by(role="student").all()}
    return render_template("manage_students_db.html", students=students, skills_by_student=skills_by_student, users_by_id=users_by_id)


@app.route("/admin/eligibility")
@admin_required
def eligibility_criteria():
    return render_template("eligibility_criteria_db.html", internships=Internship.query.filter_by(status="active", admin_approved=True).all())


@app.route("/admin/reports")
@admin_required
def admin_reports():
    internships = Internship.query.all()
    category_counts = {}
    for internship in internships:
        label = internship.category or "Uncategorised"
        category_counts[label] = category_counts.get(label, 0) + 1
    completed_profiles = sum(profile_completion(student) == 100 for student in Student.query.all())
    return render_template(
        "admin_reports_db.html",
        total_students=Student.query.count(),
        completed_profiles=completed_profiles,
        active=Internship.query.filter_by(status="active", admin_approved=True, is_active=True).count(),
        pending=Internship.query.filter_by(status="pending").count(),
        applications=Application.query.count(),
        category_counts=sorted(category_counts.items(), key=lambda item: item[1], reverse=True),
    )


@app.route("/admin/logout")
@admin_required
def admin_logout():
    logout_user()
    flash("Administrator session ended.", "success")
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    with app.app_context():
        ensure_database_schema()

    print("Database ready.")
    print("Project folder:", BASE_DIR)
    print("Static folder:", app.static_folder)

    app.run(debug=True)
