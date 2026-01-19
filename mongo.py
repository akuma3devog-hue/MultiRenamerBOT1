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
                "awaiting_thumbnail": False,
                "rename_mode": None,      # manual / auto
                "thumb_mode": False       # for future safety
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
                "thumbnail": None,
                "created_at": datetime.utcnow()
            },
            "$set": {
                "files": [],
                "rename": None,
                "awaiting_thumbnail": False,
                "rename_mode": None,      # manual / auto
                "thumb_mode": False,
                "stats": {
                    "total_files": 0,
                    "total_size": 0
                }
            }
        },
        upsert=True
    )

# =========================================================
# FILE MANAGEMENT
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
# THUMBNAIL (PERSISTENT)
# =========================================================
def set_thumbnail(user_id, file_id):
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "thumbnail": file_id,
                "thumb_updated_at": datetime.utcnow()
            }
        }
    )


def get_thumbnail(user_id):
    user = get_user(user_id)
    return user.get("thumbnail") if user else None


def delete_thumbnail(user_id):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"thumbnail": None}}
    )


# =========================================================
# THUMBNAIL MODE FLAGS (LEGACY + FUTURE)
# =========================================================
def set_awaiting_thumb(user_id, state):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"awaiting_thumbnail": state}}
    )


def is_awaiting_thumb(user_id):
    user = get_user(user_id)
    return user.get("awaiting_thumbnail", False) if user else False


def set_thumb_mode(user_id, state: bool):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"thumb_mode": state}}
    )


def is_thumb_mode(user_id):
    user = get_user(user_id)
    return user.get("thumb_mode", False) if user else False


# =========================================================
# RENAME MODE (FUTURE: MANUAL / AUTO)
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
