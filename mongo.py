from pymongo import MongoClient
import os
from datetime import datetime

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

db = client["batch_renamer"]
users = db["users"]

# ==================================================
# USER / BATCH MANAGEMENT
# ==================================================

def reset_user(user_id: int):
    users.delete_one({"user_id": user_id})


def create_user(user_id: int):
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "files": [],
            "file_count": 0,          # 🔥 ATOMIC COUNTER
            "rename": None,
            "thumbnail": None,
            "change_file_id": False,
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )


def get_user(user_id: int):
    return users.find_one({"user_id": user_id})


# ==================================================
# FILE HANDLING (ATOMIC & SAFE)
# ==================================================

def add_file(user_id: int, file_data: dict):
    """
    Atomically add file + increment count
    """
    users.update_one(
        {"user_id": user_id},
        {
            "$push": {"files": file_data},
            "$inc": {"file_count": 1}
        }
    )


def get_file_count(user_id: int) -> int:
    user = get_user(user_id)
    if not user:
        return 0
    return user.get("file_count", 0)


def get_files(user_id: int):
    user = get_user(user_id)
    if not user:
        return []
    return user.get("files", [])


# ==================================================
# RENAME CONFIGURATION
# ==================================================

def set_rename(user_id: int, rename_data: dict):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"rename": rename_data}}
    )


def get_rename(user_id: int):
    user = get_user(user_id)
    if not user:
        return None
    return user.get("rename")


def clear_rename(user_id: int):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"rename": None}}
    )


# ==================================================
# CHANGE FILE ID FLAG
# ==================================================

def set_change_file_id(user_id: int, state: bool):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"change_file_id": state}}
    )


def get_change_file_id(user_id: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    return user.get("change_file_id", False)


# ==================================================
# FULL CLEANUP (AFTER /PROCESS)
# ==================================================

def cleanup_user(user_id: int):
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "files": [],
            "file_count": 0,
            "rename": None,
            "thumbnail": None,
            "change_file_id": False
        }}
    )
