from pymongo import MongoClient
from bot.config import MONGO_URI

client = MongoClient(MONGO_URI)

db = client["batch_renamer_bot"]
users = db["users"]

def get_user(user_id: int):
    return users.find_one({"user_id": user_id})

def save_user(data: dict):
    users.update_one(
        {"user_id": data["user_id"]},
        {"$set": data},
        upsert=True
    )

def delete_user(user_id: int):
    users.delete_one({"user_id": user_id})
