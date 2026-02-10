from __future__ import annotations

import sqlite3
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = BASE_DIR / "notes.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT NOT NULL,
                bio TEXT,
                image_path TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage) -> str | None:
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        return None

    extension = filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid4().hex}.{extension}"
    relative_path = Path("uploads") / unique_name
    destination = BASE_DIR / "static" / relative_path
    file_storage.save(destination)
    return str(relative_path)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def ensure_profile(conn: sqlite3.Connection, user_id: int, username: str) -> sqlite3.Row:
    profile = conn.execute("SELECT * FROM profile WHERE user_id = ?", (user_id,)).fetchone()
    if profile:
        return profile
    conn.execute(
        "INSERT INTO profile (user_id, username, bio, image_path) VALUES (?, ?, ?, ?)",
        (user_id, username, "", None),
    )
    return conn.execute("SELECT * FROM profile WHERE user_id = ?", (user_id,)).fetchone()


@app.before_request
def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    with get_db() as conn:
        g.user = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()


@app.route("/")
def root():
    if g.user:
        return redirect(url_for("index"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("register"))
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
            ensure_profile(conn, user_id, username)
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))
        session.clear()
        session["user_id"] = user["id"]
        flash("Welcome back!", "success")
        return redirect(url_for("index"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def index():
    with get_db() as conn:
        profile = ensure_profile(conn, g.user["id"], g.user["username"])
        notes = conn.execute(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (g.user["id"],),
        ).fetchall()
    return render_template("index.html", profile=profile, notes=notes, user=g.user)


@app.post("/update_profile")
@login_required
def update_profile():
    username = request.form.get("username", "").strip()
    bio = request.form.get("bio", "").strip()
    uploaded = save_upload(request.files.get("profile_image"))
    with get_db() as conn:
        if uploaded:
            conn.execute(
                "UPDATE profile SET username = ?, bio = ?, image_path = ? WHERE user_id = ?",
                (username, bio, uploaded, g.user["id"]),
            )
        else:
            conn.execute(
                "UPDATE profile SET username = ?, bio = ? WHERE user_id = ?",
                (username, bio, g.user["id"]),
            )
    flash("Profile updated.", "success")
    return redirect(url_for("index"))


@app.post("/notes")
@login_required
def create_note():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    if not title or not body:
        flash("Title and content are required.", "error")
        return redirect(url_for("index"))
    uploaded = save_upload(request.files.get("note_image"))
    with get_db() as conn:
        conn.execute(
            "INSERT INTO notes (user_id, title, body, image_path) VALUES (?, ?, ?, ?)",
            (g.user["id"], title, body, uploaded),
        )
    flash("Note added.", "success")
    return redirect(url_for("index"))


# --- YENİ EKLENEN FONKSİYONLAR ---

@app.post("/delete_note/<int:note_id>")
@login_required
def delete_note(note_id):
    with get_db() as conn:
        conn.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, g.user["id"]))
    flash("Note deleted.", "success")
    return redirect(url_for("index"))


@app.post("/edit_note/<int:note_id>")
@login_required
def edit_note(note_id):
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    if not title or not body:
        flash("Title and content are required.", "error")
        return redirect(url_for("index"))
    
    with get_db() as conn:
        conn.execute(
            "UPDATE notes SET title = ?, body = ? WHERE id = ? AND user_id = ?",
            (title, body, note_id, g.user["id"])
        )
    flash("Note updated.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)