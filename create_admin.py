"""Create one local SIMS administrator account from the command line."""
from getpass import getpass

from werkzeug.security import generate_password_hash

from app import app, ensure_database_schema
from models import User, db


def main():
    with app.app_context():
        ensure_database_schema()
        name = input("Administrator name: ").strip()
        email = input("Administrator email: ").strip().lower()
        password = getpass("Password (at least 8 characters): ")
        if not name or "@" not in email or len(password) < 8:
            raise SystemExit("Enter a name, a valid email, and a password of at least 8 characters.")
        if User.query.filter_by(email=email).first():
            raise SystemExit("That email already has a SIMS account.")
        db.session.add(User(name=name, email=email, password_hash=generate_password_hash(password), role="admin"))
        db.session.commit()
        print("Administrator account created. Sign in at /admin/login.")


if __name__ == "__main__":
    main()
