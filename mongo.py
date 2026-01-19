# mongo.py
from pymongo import MongoClient
from datetime import datetime
import os

client = MongoClient(os.getenv("MONGO_URI"))
db = client["multi_renamer"]
users = db["users"]

# =========================================================
# CORE USER RESET / CREATE
# =========================================================
def reset_user(user_id):
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "files": [],
                "rename": None,
                "rename_mode": None
            }
        },
        upsert=True
    )


def create_user(user_id):
    users.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            },
            "$set": {
                "files": [],
                "rename": None,
                "rename_mode": None,
                "stats": {
                    "total_files": 0,
                    "total_size": 0
                }
            }
        },
        upsert=True
    )

# =========================================================
# FILE QUEUE MANAGEMENT
# =========================================================
def add_file(user_id, file):
    users.update_one(
        {"user_id": user_id},
        {
            "$push": {"files": file},
            "$inc": {
                "stats.total_files": 1,
                "stats.total_size": file.get("size", 0)
            }
        }
    )


def clear_files(user_id):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"files": []}}
    )


def get_user(user_id):
    return users.find_one({"user_id": user_id})

# =========================================================
# RENAME MODE (OPTIONAL / FUTURE USE)
# =========================================================
def set_rename_mode(user_id, mode: str | None):
    """
    mode = 'manual' | 'auto' | None
    """
    users.update_one(
        {"user_id": user_id},
        {"$set": {"rename_mode": mode}}
    )


def get_rename_mode(user_id):
    user = get_user(user_id)
    return user.get("rename_mode") if user else None
