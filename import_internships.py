"""Import administrator-reviewed internships from a CSV into SIMS SQLite.

Required columns: title, company, source_name, source_url, application_url
Optional columns: slug, location, mode, duration, stipend, deadline,
qualification, year, category, required_skills, description, is_active
"""
import csv
import re
import sys

from app import app, ensure_database_schema
from models import Internship, db


def make_slug(title, company):
    value = f"{title}-{company}".lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def import_csv(filename):
    with app.app_context(), open(filename, newline="", encoding="utf-8-sig") as file:
        ensure_database_schema()
        reader = csv.DictReader(file)
        required = {"title", "company", "source_name", "source_url", "application_url"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("CSV needs: " + ", ".join(sorted(required)))

        imported = 0
        for row in reader:
            if not all((row.get(key) or "").strip() for key in required):
                continue
            internship = Internship.query.filter_by(source_url=row["source_url"].strip()).first()
            is_new = internship is None
            if internship is None:
                internship = Internship()
                db.session.add(internship)
            internship.slug = (row.get("slug") or make_slug(row["title"], row["company"])).strip()
            for field in ("title", "company", "location", "mode", "duration", "stipend", "deadline", "qualification", "year", "category", "required_skills", "description", "application_url", "source_name", "source_url"):
                if field in row:
                    setattr(internship, field, row[field].strip())
            # CSV imports use the same safe review queue as live imports.
            # Existing administrator decisions are retained on re-import.
            if is_new:
                internship.status = "pending"
                internship.admin_approved = False
                internship.is_active = False
            imported += 1
        db.session.commit()
        return imported


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python import_internships.py path\\to\\internships.csv")
    print(f"Imported {import_csv(sys.argv[1])} internship(s).")
