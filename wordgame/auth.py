import functools
import sqlite3

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .rules import password_problems, username_problems

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def home_for(user):
    return url_for("admin.daily_report") if user["role"] == "admin" else url_for("game.dashboard")


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            flash("Log in to continue.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)
    return wrapped


def role_required(role):
    def decorator(view):
        @functools.wraps(view)
        @login_required
        def wrapped(**kwargs):
            if g.user["role"] != role:
                abort(403)
            return view(**kwargs)
        return wrapped
    return decorator


@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(home_for(g.user))

    errors = {}
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if problems := username_problems(username):
            errors["username"] = problems
        if problems := password_problems(password):
            errors["password"] = problems

        if not errors:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'player')",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                errors["username"] = [f"{username} is taken. Pick another username."]
            else:
                session.clear()
                session["user_id"] = cur.lastrowid
                flash(f"Account created. Welcome, {username}.", "success")
                return redirect(url_for("game.dashboard"))

    status = 400 if errors else 200
    return render_template("auth/register.html", errors=errors, username=username), status


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(home_for(g.user))

    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, role, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "That username and password don't match. Check both and try again."
        else:
            session.clear()
            session["user_id"] = user["id"]
            target = request.args.get("next", "")
            # Only follow local paths, never an external URL.
            if not target.startswith("/") or target.startswith("//"):
                target = home_for(user)
            return redirect(target)

    return render_template("auth/login.html", error=error, username=username), (401 if error else 200)


@bp.post("/logout")
def logout():
    session.clear()
    flash("You're logged out.", "info")
    return redirect(url_for("auth.login"))
