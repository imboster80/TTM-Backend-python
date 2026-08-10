import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

# 4. Database Connection Check
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise Exception("MONGO_URI is not set in Environment Variables!")

client = AsyncIOMotorClient(MONGO_URI)
# Database နာမည်အမှန်ကို ဤနေရာတွင် ထည့်ပါ
db = client["ttm_db"]
