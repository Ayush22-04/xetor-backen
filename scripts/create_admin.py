#!/usr/bin/env python3
"""Small helper to create an admin user in the MongoDB collection.

Usage:
  ./scripts/create_admin.py
"""
import getpass
import os
import sys

# Ensure the project root is on sys.path so `app` package can be imported
# when this script is executed directly from the `scripts/` folder.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.extensions.db import get_db
from app.models.models import ADMIN_USERS
import bcrypt


def main():
    username = input("username: ")
    password = getpass.getpass("password: ")
    if not username or not password:
        print("username and password required")
        return

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db = get_db()
    db[ADMIN_USERS].insert_one({"username": username, "password": hashed})
    print("Created admin user:", username)


if __name__ == "__main__":
    main()
