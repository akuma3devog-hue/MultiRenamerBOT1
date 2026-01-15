from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["batch_renamer"]
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
            "change_file_id": False
        }},
        upsert=True
    )
