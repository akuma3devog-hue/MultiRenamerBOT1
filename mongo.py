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
    """
    Completely remove user batch data
    """
    users.delete_one({"user_id": user_id})


def create_user(user_id: int):
    """
    Create a fresh batch state for the user
    """
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "files": [],
            "rename": None,
            "thumbnail": None,
            "change_file_id": False,
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )


def get_user(user_id: int):
    """
    Get full user document
    """
    return users.find_one({"user_id": user_id})


# ==================================================
# FILE HANDLING
# ==================================================

def add_file(user_id: int, file_data: dict):
    """
    Add a file to the user's batch (order preserved)
    """
    users.update_one(
        {"user_id": user_id},
        {"$push": {"files": file_data}}
    )


def get_files(user_id: int):
    """
    Get list of uploaded files for user
    """
    user = get_user(user_id)
    if not user:
        return []
    return user.get("files", [])


def clear_files(user_id: int):
    """
    Clear all files after /process
    """
    users.update_one(
        {"user_id": user_id},
        {"$set": {"files": []}}
    )


# ==================================================
# RENAME CONFIGURATION
# ==================================================

def set_rename(user_id: int, rename_data: dict):
    """
    Save rename pattern:
    {
        base: str,
        season: int,
        episode: int,
        zero_pad: bool
    }
    """
    users.update_one(
        {"user_id": user_id},
        {"$set": {"rename": rename_data}}
    )


def get_rename(user_id: int):
    """
    Get rename configuration
    """
    user = get_user(user_id)
    if not user:
        return None
    return user.get("rename")


def clear_rename(user_id: int):
    """
    Remove rename config after /process
    """
    users.update_one(
        {"user_id": user_id},
        {"$set": {"rename": None}}
    )


# ==================================================
# CHANGE FILE ID FLAG
# ==================================================

def set_change_file_id(user_id: int, state: bool):
    """
    Enable or disable /changefileid
    """
    users.update_one(
        {"user_id": user_id},
        {"$set": {"change_file_id": state}}
    )


def get_change_file_id(user_id: int) -> bool:
    """
    Get /changefileid state
    """
    user = get_user(user_id)
    if not user:
        return False
    return user.get("change_file_id", False)


# ==================================================
# FULL CLEANUP (AFTER /PROCESS)
# ==================================================

def cleanup_user(user_id: int):
    """
    Reset batch but keep user document
    """
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "files": [],
            "rename": None,
            "thumbnail": None,
            "change_file_id": False
        }}
    )
