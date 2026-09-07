"""Initialise the local SIMS database without inserting sample records."""
from app import app, ensure_database_schema


with app.app_context():
    ensure_database_schema()
    print("SIMS database schema is ready. Use the Admin Sources page to import roles for review.")
