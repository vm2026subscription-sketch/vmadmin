import os
from datetime import datetime

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from werkzeug.security import generate_password_hash

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "vmadmin")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set")

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = client[MONGO_DB_NAME]
admins_col = db["admins"]
admins_col.create_index([("username", ASCENDING)], unique=True)

seed_admins = [
    ("admin1", "password1"),
    ("admin2", "password2"),
    ("admin3", "password3"),
]

created = 0
skipped = 0

for username, password in seed_admins:
    existing = admins_col.find_one({"username": username})
    if existing:
        skipped += 1
        continue

    admins_col.insert_one({
        "username": username,
        "password_hash": generate_password_hash(password),
        "createdAt": datetime.utcnow(),
    })
    created += 1

print(f"Admins created: {created}, skipped: {skipped}")
