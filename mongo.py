from pymongo import MongoClient
from datetime import datetime
import os

client = MongoClient(os.getenv("MONGO_URI"))
db = client["multi_renamer"]
users = db["users"]

def reset_user(user_id):
    users.delete_one({"user_id": user_id})

def create_user(user_id):
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "files": [],
            "rename": None,
            "thumbnail": None,
            "awaiting_thumbnail": False,
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )

def add_file(user_id, file):
    users.update_one({"user_id": user_id}, {"$push": {"files": file}})

def get_user(user_id):
    return users.find_one({"user_id": user_id})

def get_files(user_id):
    user = get_user(user_id)
    return user["files"] if user else []

# ---------- THUMBNAIL ----------
def set_thumbnail(user_id, file_id):
    users.update_one({"user_id": user_id}, {"$set": {"thumbnail": file_id}})

def get_thumbnail(user_id):
    user = get_user(user_id)
    return user.get("thumbnail") if user else None

def delete_thumbnail(user_id):
    users.update_one({"user_id": user_id}, {"$set": {"thumbnail": None}})

def set_awaiting_thumb(user_id, state: bool):
    users.update_one({"user_id": user_id}, {"$set": {"awaiting_thumbnail": state}})

def is_awaiting_thumb(user_id):
    user = get_user(user_id)
    return user.get("awaiting_thumbnail", False) if user else False
