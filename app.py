import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from pymongo import ASCENDING, DESCENDING, MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me")

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "vmadmin")
SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set")

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = client[MONGO_DB_NAME]
admins_col = db["admins"]
epapers_col = db["epapers"]

admins_col.create_index([("username", ASCENDING)], unique=True)
epapers_col.create_index([("date", DESCENDING)])
epapers_col.create_index([("publisher", ASCENDING), ("language", ASCENDING)])


def login_required(handler):
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login"))
        return handler(*args, **kwargs)

    wrapper.__name__ = handler.__name__
    return wrapper


def build_paper(form):
    date_str = form.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
    language = form.get("language") or "English"
    title = form.get("title") or f"Vidyarthi Mitra {language} - {date_str}"
    url = (form.get("url") or form.get("link") or form.get("fileUrl") or "").strip()

    paper = {
        "id": str(int(datetime.utcnow().timestamp() * 1000)),
        "title": title,
        "publisher": "Vidyarthi Mitra",
        "language": language,
        "category": "Vidyarthi Mitra",
        "date": date_str,
        "fileUrl": "",
        "link": url,
        "edition": "Daily Edition",
        "pages": "—",
        "size": "—",
        "description": f"Vidyarthi Mitra {language} edition for {date_str}",
        "views": 0,
        "downloads": 0,
        "tags": ["Vidyarthi Mitra"],
        "featured": False,
        "createdAt": datetime.utcnow(),
    }

    return paper


@app.route("/")
def index():
    if session.get("admin_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if admins_col.count_documents({}) > 0:
        return "Setup already completed", 403

    token = request.args.get("token") or request.form.get("token")
    if SETUP_TOKEN and token != SETUP_TOKEN:
        return "Invalid setup token", 403

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Username and password are required.")
            return render_template("setup.html")

        password_hash = generate_password_hash(password)
        admins_col.insert_one({
            "username": username,
            "password_hash": password_hash,
            "createdAt": datetime.utcnow(),
        })
        flash("Admin created. Please log in.")
        return redirect(url_for("login"))

    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        admin = admins_col.find_one({"username": username})
        if not admin or not check_password_hash(admin["password_hash"], password):
            flash("Invalid username or password.")
            return render_template("login.html")

        session["admin_id"] = str(admin["_id"])
        session["admin_username"] = admin["username"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    query = {}
    language = request.args.get("language") or ""
    date_str = request.args.get("date") or ""

    if language and language != "All":
        query["language"] = language
    if date_str:
        query["date"] = date_str

    papers = list(epapers_col.find(query, {"_id": 0}).sort("date", DESCENDING).limit(200))
    
    # Get unique dates for filter dropdown
    unique_dates = sorted(
        list(set(p["date"] for p in epapers_col.find({}, {"date": 1, "_id": 0}))),
        reverse=True
    )

    return render_template(
        "dashboard.html",
        papers=papers,
        selected_language=language,
        selected_date=date_str,
        available_dates=unique_dates,
    )


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if request.method == "POST":
        if not (request.form.get("url") or request.form.get("link") or request.form.get("fileUrl")):
            flash("Please provide a PDF URL.")
            return render_template("upload.html", today=today)

        paper = build_paper(request.form)
        epapers_col.insert_one(paper)
        flash("Paper uploaded successfully.")
        return redirect(url_for("dashboard"))

    return render_template("upload.html", today=today)


@app.route("/edit/<paper_id>", methods=["GET", "POST"])
@login_required
def edit_paper(paper_id):
    paper = epapers_col.find_one({"id": paper_id}, {"_id": 0})
    if not paper:
        flash("Paper not found.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        url = (request.form.get("url") or "").strip()
        if not url:
            flash("Please provide a PDF URL.")
            return render_template("edit.html", paper=paper)

        epapers_col.update_one(
            {"id": paper_id},
            {
                "$set": {
                    "date": request.form.get("date") or paper["date"],
                    "language": request.form.get("language") or paper["language"],
                    "title": request.form.get("title") or paper["title"],
                    "link": url,
                }
            },
        )
        flash("Paper updated successfully.")
        return redirect(url_for("dashboard"))

    return render_template("edit.html", paper=paper)


@app.route("/delete/<paper_id>", methods=["POST"])
@login_required
def delete_paper(paper_id):
    result = epapers_col.delete_one({"id": paper_id})
    if result.deleted_count > 0:
        flash("Paper deleted successfully.")
    else:
        flash("Paper not found.")
    return redirect(url_for("dashboard"))


@app.route("/api/epapers", methods=["GET"])
def api_epapers():
    query = {}
    language = request.args.get("language")
    publisher = request.args.get("publisher")
    date_str = request.args.get("date")

    if language:
        query["language"] = language
    if publisher:
        query["publisher"] = publisher
    if date_str:
        query["date"] = date_str

    limit = request.args.get("limit", "200")
    try:
        limit_value = max(1, min(int(limit), 500))
    except ValueError:
        limit_value = 200

    papers = list(epapers_col.find(query, {"_id": 0}).sort("date", DESCENDING).limit(limit_value))
    return jsonify({"items": papers})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
