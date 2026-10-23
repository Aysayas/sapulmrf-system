"""Admin commands. Run inside the api container:

    docker compose exec api python -m app.cli create-admin
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.activity.service import log
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.users.models import User


def create_admin(db: Session, name: str, username: str, password: str) -> User:
    if len(password) < 8:
        raise ValueError("Use at least 8 characters.")
    if db.scalar(select(User).where(User.username == username)):
        raise ValueError(f"The username {username!r} is already taken.")
    user = User(name=name, username=username, password_hash=hash_password(password), role="admin")
    db.add(user)
    db.flush()
    log(db, None, "Created first administrator", f"{name} ({username})")
    db.commit()
    return user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    ca = sub.add_parser("create-admin", help="create a Barangay Administrator account")
    ca.add_argument("--name", default=None)
    ca.add_argument("--username", default=None)
    args = parser.parse_args(argv)

    name = args.name or input("Full name: ").strip()
    username = args.username or input("Username: ").strip()
    password = getpass.getpass("Password (8+ characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords don't match.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            create_admin(db, name, username, password)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
    print(f"Administrator {username!r} created. Log in at http://localhost:5174")
    return 0


if __name__ == "__main__":
    sys.exit(main())
