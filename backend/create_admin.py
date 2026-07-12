"""
Run this once after setting up the database to create your first admin
account with a properly generated password hash.

Usage:
    python create_admin.py
"""

import getpass

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User


def main():
    app = create_app()
    with app.app_context():
        username = input("Username [admin]: ").strip() or "admin"
        full_name = input("Full name [Library Administrator]: ").strip() or "Library Administrator"
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("Passwords do not match. Aborting.")
            return

        existing = User.query.filter_by(username=username).first()
        if existing:
            existing.password_hash = generate_password_hash(password)
            existing.full_name = full_name
            db.session.commit()
            print(f"Updated existing user '{username}'.")
            return

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            full_name=full_name,
            role="admin",
        )
        db.session.add(user)
        db.session.commit()
        print(f"Created admin user '{username}'.")


if __name__ == "__main__":
    main()
