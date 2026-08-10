import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017/ttm_db"

client = AsyncIOMotorClient(MONGO_URI)
# Database နာမည်ကို တိုက်ရိုက်သတ်မှတ်ပေးခြင်း
db = client.get_database("ttm_db")
