from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, redirect, render_template, request, url_for
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


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL,
                bio TEXT,
                image_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO profile (id, username, bio, image_path)
            VALUES (1, 'My Notes Profile', 'Capture your thoughts with image notes.', NULL)
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


init_db()


@app.route("/")
def index():
    with get_db() as conn:
        profile = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        notes = conn.execute("SELECT * FROM notes ORDER BY created_at DESC, id DESC").fetchall()
    return render_template("index.html", profile=profile, notes=notes)


@app.post("/profile")
def update_profile():
    username = request.form.get("username", "").strip()
    bio = request.form.get("bio", "").strip()

    if not username:
        flash("Profile name is required.", "error")
        return redirect(url_for("index"))

    uploaded = save_upload(request.files.get("profile_image"))
    if request.files.get("profile_image") and not uploaded and request.files.get("profile_image").filename:
        flash("Profile image must be png, jpg, jpeg, gif, or webp.", "error")
        return redirect(url_for("index"))

    with get_db() as conn:
        if uploaded:
            conn.execute(
                "UPDATE profile SET username = ?, bio = ?, image_path = ? WHERE id = 1",
                (username, bio, uploaded),
            )
        else:
            conn.execute(
                "UPDATE profile SET username = ?, bio = ? WHERE id = 1",
                (username, bio),
            )

    flash("Profile updated.", "success")
    return redirect(url_for("index"))


@app.post("/notes")
def create_note():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()

    if not title or not body:
        flash("Note title and content are required.", "error")
        return redirect(url_for("index"))

    uploaded = save_upload(request.files.get("note_image"))
    if request.files.get("note_image") and not uploaded and request.files.get("note_image").filename:
        flash("Note image must be png, jpg, jpeg, gif, or webp.", "error")
        return redirect(url_for("index"))

    with get_db() as conn:
        conn.execute(
            "INSERT INTO notes (title, body, image_path) VALUES (?, ?, ?)",
            (title, body, uploaded),
        )

    flash("Note added successfully.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)