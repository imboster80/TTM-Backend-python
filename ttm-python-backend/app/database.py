import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise Exception("MONGO_URI not found in Environment Variables!")

client = AsyncIOMotorClient(MONGO_URI)
db = client["ttm_db"] # Database နာမည်က ttm_db ဖြစ်ပါတယ်
