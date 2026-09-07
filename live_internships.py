"""Synchronise live internship records from OpenIntern's public API.

OpenIntern supplies active employer-ATS postings and direct application links.
The API has role/category data but not full descriptions, so this project never
pretends inferred topic matches are employer-stated skill requirements.
"""
import json
import re
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

from app import app, ensure_database_schema
from models import Internship, InternshipSource, db

API_URL = "https://openintern.dev/api/v1/jobs"


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def sync_live_internships(limit=40):
    query = urlencode({"limit": limit})
    with urlopen(f"{API_URL}?{query}", timeout=30) as response:
        payload = json.load(response)

    with app.app_context():
        ensure_database_schema()
        imported = 0
        for family in payload.get("jobs", []):
            company = family.get("company", {}).get("name", "Unknown company")
            roles = family.get("roles", [])
            category = ", ".join(roles) if roles else "Internship"
            for posting in family.get("postings", []):
                application_url = posting.get("apply_url")
                if not application_url:
                    continue
                internship = Internship.query.filter_by(source_url=application_url).first()
                is_new = internship is None
                if internship is None:
                    internship = Internship()
                    db.session.add(internship)
                internship.slug = "openintern-" + slugify(posting.get("id", application_url))
                internship.title = posting.get("title") or family.get("title")
                internship.company = company
                internship.location = posting.get("location") or "Location not listed"
                internship.mode = "Remote" if "remote" in str(posting.get("location", "")).lower() else "See employer listing"
                internship.duration = "See employer listing"
                internship.stipend = "Not listed"
                internship.deadline = "See employer listing"
                internship.qualification = "See employer listing"
                internship.year = "See employer listing"
                internship.category = category
                internship.required_skills = ""  # No invented employer requirements.
                internship.description = family.get("title", "")
                internship.application_url = application_url
                internship.source_name = "OpenIntern (employer ATS link)"
                internship.source_url = application_url
                internship.external_id = posting.get("id")
                internship.imported_at = datetime.utcnow()
                # Imported records always enter the review queue. Existing
                # administrator decisions are deliberately preserved on sync.
                if is_new:
                    internship.status = "pending"
                    internship.admin_approved = False
                    internship.is_active = False
                imported += 1
        source = InternshipSource.query.filter_by(name="OpenIntern").first()
        if source is None:
            source = InternshipSource(name="OpenIntern", endpoint=API_URL)
            db.session.add(source)
        source.enabled = True
        source.last_sync_at = datetime.utcnow()
        source.last_import_count = imported
        db.session.commit()
        return imported


if __name__ == "__main__":
    print(f"Synced {sync_live_internships()} live internship postings.")
