from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["batch_renamer"]
users = db["users"]

# -------- USER / BATCH --------

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
            "change_file_id": False
        }},
        upsert=True
    )

def get_user(user_id):
    return users.find_one({"user_id": user_id})

# -------- FILE HANDLING --------

def add_file(user_id, file_data):
    users.update_one(
        {"user_id": user_id},
        {"$push": {"files": file_data}}
    )

def get_files(user_id):
    user = get_user(user_id)
    return user["files"] if user else []

# -------- RENAME --------

def set_rename(user_id, rename_data):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"rename": rename_data}}
    )
