from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_user_id"):
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("admin.login"))
        return fn(*args, **kwargs)

    return wrapper


def current_admin():
    """Return the currently logged in admin username or None."""
    return session.get("admin_username")
