"""Create (or update the password/role of) an analyst/admin login.

Usage:
    python -m app.scripts.create_user analyst@bank.com --password secret123 --role analyst
"""
import argparse

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="analyst", choices=["analyst", "admin"])
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).one_or_none()
        if user is None:
            user = User(email=args.email, password_hash=hash_password(args.password), role=args.role)
            db.add(user)
            action = "Created"
        else:
            user.password_hash = hash_password(args.password)
            user.role = args.role
            action = "Updated"
        db.commit()
        print(f"{action} user {args.email} (role={args.role})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
