import os, datetime, jwt, logging
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from bson import ObjectId
from passlib.context import CryptContext
from app.database import db
from app.utils import solve_image_ocr

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET", "ttm_secret_key_2026")
ALGORITHM = "HS256"
HARDCODED_DEV_TOKEN = "ttm_master_dev_token_2026"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str = Field(..., max_length=71)
    role: str = "User"

class ProfileData(BaseModel):
    profile_name: str
    bot_token: str
    admin_id: str

class CreateCodeRequest(BaseModel):
    code: str
    hours: float
    max_uses: int

class RedeemCodeRequest(BaseModel):
    code: str

# --- Helper functions ---
def fix_id(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = auth_header.split(" ")[1] if " " in auth_header else auth_header
    
    # Check Bypass Token
    if token == HARDCODED_DEV_TOKEN:
        # Developer အတွက် Database ထဲမှာ အကောင့်ရှိမရှိ အရင်စစ်မယ်
        dev_user = await db["users"].find_one({"username": "MrTanTawMoe"})
        if dev_user:
            return dev_user
        else:
            # အကောင့်မရှိသေးရင် ယာယီ ID တစ်ခု ပေးထားမယ်
            return {"_id": ObjectId("000000000000000000000000"), "username": "MrTanTawMoe", "role": "Developer"}

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user = await db["users"].find_one({"_id": ObjectId(payload.get("id"))})
        if not user: raise HTTPException(status_code=401, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# --- APIs ---

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    try:
        # Collection ခေါ်တာကို db["users"] လို့ ပြောင်းလိုက်တယ်နော်
        existing = await db["users"].find_one({"username": req.username})
        if existing: return {"success": False, "detail": "အကောင့်နာမည် ရှိနှင့်ပြီးသားဖြစ်နေပါတယ်"}
        
        # Developer နာမည်နဲ့ ဖွင့်ရင် Role ကို Developer လို့ အလိုအလျောက် သတ်မှတ်ပေးမယ်
        assigned_role = "Developer" if req.username == "MrTanTawMoe" else req.role
        
        new_user = {
            "username": req.username,
            "password_hash": pwd_context.hash(req.password),
            "role": assigned_role,
            "vip_expiry": None,
            "is_banned": False,
            "created_at": datetime.datetime.utcnow()
        }
        await db["users"].insert_one(new_user)
        return {"success": True, "message": f"အကောင့်သစ်ကို {assigned_role} အဖြစ် ဖွင့်လှစ်ပြီးပါပြီ"}
    except Exception as e:
        logger.error(f"Registration Error: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "detail": f"Database Error: {str(e)}"})

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    try:
        user = await db["users"].find_one({"username": req.username})
        if not user or user.get("is_banned") or not pwd_context.verify(req.password, user["password_hash"]):
            return {"success": False, "detail": "ယူဆာအမည် သို့မဟုတ် လျှို့ဝှက်နံပါတ် မှားယွင်းနေပါတယ်"}
        
        token = jwt.encode({"id": str(user["_id"]), "role": user["role"]}, JWT_SECRET, algorithm=ALGORITHM)
        return {"success": True, "token": token, "role": user["role"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "detail": str(e)})

@app.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    now = datetime.datetime.utcnow()
    expiry = user.get("vip_expiry")
    is_vip = expiry is not None and expiry > now
    return {
        "success": True,
        "user": {
            "_id": str(user["_id"]),
            "username": user["username"],
            "role": user["role"],
            "vip_expiry": str(expiry) if expiry else None,
            "isVip": is_vip or user["role"] == "Developer" # Developer ဆိုရင် အမြဲ VIP ဖြစ်အောင် လုပ်ပေးထားတယ်နော်
        }
    }

# --- ကျန်တဲ့ APIs တွေမှာလည်း db.profiles အစား db["profiles"] လို့ ပြောင်းသုံးပေးပါဦးနော် ---
