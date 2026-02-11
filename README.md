# WebsiteDesigningProject
# Notes Profile Website (Flask)

A Flask web app where each user can:

- Register and log in with email/password
- Save a personal profile (name, bio, profile image)
- Create notes with optional images
- Continue from where they left off after logging back in (data is stored per user in SQLite)
- Edit notes that are already existing within their profile
- Delete existing notes in profile

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5001`.

## Routes

- `GET/POST /register` → create account
- `GET/POST /login` → sign in
- `POST /logout` → sign out
- `GET /dashboard` → notes/profile page (requires login)
- `POST /profile` → update profile (requires login)
- `POST /notes` → add note (requires login)

## Tech

- Flask
- SQLite (`sqlite3`)
- Jinja templates + CSS
