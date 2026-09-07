from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    qualification = db.Column(db.String(100))
    specialization = db.Column(db.String(100))
    year = db.Column(db.String(50))
    skills = db.Column(db.Text)
    phone = db.Column(db.String(20))
    resume_path = db.Column(db.String(255))


class StudentSkill(db.Model):
    __tablename__ = "student_skills"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )
    skill = db.Column(db.String(100), nullable=False)


class Internship(db.Model):
    __tablename__ = "internships"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(150), unique=True)
    title = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(100))
    mode = db.Column(db.String(50))
    duration = db.Column(db.String(50))
    stipend = db.Column(db.String(50))
    deadline = db.Column(db.String(50))
    qualification = db.Column(db.String(100))
    year = db.Column(db.String(50))
    category = db.Column(db.String(100))
    required_skills = db.Column(db.Text)
    description = db.Column(db.Text)
    application_url = db.Column(db.String(500))
    source_name = db.Column(db.String(100))
    source_url = db.Column(db.String(500), unique=True)
    external_id = db.Column(db.String(150))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")
    admin_approved = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)


class InternshipSource(db.Model):
    """A small audit record for each external source used by SIMS."""
    __tablename__ = "internship_sources"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    last_sync_at = db.Column(db.DateTime)
    last_import_count = db.Column(db.Integer, default=0)


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id"))
    status = db.Column(db.String(30), default="Applied")
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    
