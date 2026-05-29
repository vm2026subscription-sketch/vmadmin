import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "vmadmin")

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = client[MONGO_DB_NAME]
admins_col = db["admins"]

admins = list(admins_col.find({}, {"username": 1, "role": 1}))
print("\nCurrent admins:")
for a in admins:
    role = a.get("role", "admin (no role set)")
    print(f"  - {a['username']}  [{role}]")

if len(sys.argv) < 2:
    print("\nUsage: python make_super_admin.py <username>")
    print("Example: python make_super_admin.py admin1")
    sys.exit(1)

target = sys.argv[1]
result = admins_col.update_one({"username": target}, {"$set": {"role": "super_admin"}})

if result.matched_count == 0:
    print(f"\nError: Admin '{target}' not found.")
    sys.exit(1)

print(f"\nDone! '{target}' is now super_admin.")
print("Ab logout karke dobara login karo.")
