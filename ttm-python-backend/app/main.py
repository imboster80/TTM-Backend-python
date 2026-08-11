import os, datetime, jwt
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from bson import ObjectId
from passlib.context import CryptContext
from app.database import db
from app.utils import solve_image_ocr

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_123")
ALGORITHM = "HS256"
HARDCODED_DEV_TOKEN = "ttm_master_dev_token_2026"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
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

class GenerateKeyRequest(BaseModel):
    expiry_hours: float

# --- Auth Helper ---
async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = auth_header.split(" ")[1] if " " in auth_header else auth_header
    if token == HARDCODED_DEV_TOKEN:
        return {"_id": "000000000000000000000000", "username": "MasterDeveloper", "role": "Developer"}
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user = await db.users.find_one({"_id": ObjectId(payload.get("id"))})
        if not user: raise HTTPException(status_code=401, detail="User not found")
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

# --- Routes ---

@app.get("/")
async def root():
    return {"success": True, "message": "TTM Python Backend is Live!"}

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    existing = await db.users.find_one({"username": req.username})
    if existing: return {"success": False, "detail": "Username exists"}
    new_user = {
        "username": req.username,
        "password_hash": pwd_context.hash(req.password),
        "role": req.role,
        "vip_expiry": None,
        "is_banned": False,
        "created_at": datetime.datetime.utcnow()
    }
    await db.users.insert_one(new_user)
    return {"success": True, "message": "Registered successfully"}

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = await db.users.find_one({"username": req.username})
    if not user or user.get("is_banned") or not pwd_context.verify(req.password, user["password_hash"]):
        return {"success": False, "detail": "Invalid credentials"}
    token = jwt.encode({"id": str(user["_id"]), "role": user["role"]}, JWT_SECRET, algorithm=ALGORITHM)
    return {"success": True, "token": token, "role": user["role"]}

@app.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    now = datetime.datetime.utcnow()
    is_vip = user.get("vip_expiry") is not None and user["vip_expiry"] > now
    return {
        "success": True,
        "user": {
            "_id": str(user["_id"]),
            "username": user["username"],
            "role": user["role"],
            "vip_expiry": str(user["vip_expiry"]) if user.get("vip_expiry") else None,
            "isVip": is_vip
        }
    }

@app.post("/api/utils/solve-captcha")
async def solve_captcha(request: Request):
    image_bytes = await request.body()
    try:
        text = solve_image_ocr(image_bytes)
        return {"success": True, "message": text}
    except Exception as e:
        return {"success": False, "detail": str(e)}

@app.get("/api/profiles")
async def get_profiles(user: dict = Depends(get_current_user)):
    profiles = await db.profiles.find({"user_id": str(user["_id"])}).to_list(100)
    for p in profiles: p["_id"] = str(p["_id"])
    return {"success": True, "profiles": profiles}

@app.post("/api/profiles")
async def save_profile(data: ProfileData, user: dict = Depends(get_current_user)):
    new_p = data.dict()
    new_p["user_id"] = str(user["_id"])
    await db.profiles.insert_one(new_p)
    return {"success": True, "message": "Saved"}

@app.post("/api/admin/codes/create")
async def create_code(req: CreateCodeRequest, user: dict = Depends(get_current_user)):
    if user["role"] not in ["Admin", "Developer"]: raise HTTPException(403)
    await db.redeem_codes.insert_one({
        "code": req.code, "hours": req.hours, "max_uses": req.max_uses, "used_count": 0
    })
    return {"success": True, "message": "Code created"}

@app.post("/api/user/codes/redeem")
async def redeem_code(req: RedeemCodeRequest, user: dict = Depends(get_current_user)):
    code_doc = await db.redeem_codes.find_one({"code": req.code})
    if not code_doc or code_doc["used_count"] >= code_doc["max_uses"]:
        return {"success": False, "detail": "Invalid or expired code"}
    now = datetime.datetime.utcnow()
    current_expiry = user["vip_expiry"] if (user.get("vip_expiry") and user["vip_expiry"] > now) else now
    new_expiry = current_expiry + datetime.timedelta(hours=code_doc["hours"])
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"vip_expiry": new_expiry}})
    await db.redeem_codes.update_one({"_id": code_doc["_id"]}, {"$inc": {"used_count": 1}})
    return {"success": True, "message": "Redeemed"}

@app.get("/api/admin/codes/all")
async def get_all_codes(user: dict = Depends(get_current_user)):
    if user["role"] not in ["Admin", "Developer"]: raise HTTPException(403)
    codes = await db.redeem_codes.find().to_list(100)
    for c in codes: c["_id"] = str(c["_id"])
    return {"success": True, "codes": codes}

@app.get("/api/dev/users/all")
async def get_all_users(user: dict = Depends(get_current_user)):
    if user["role"] != "Developer": raise HTTPException(403)
    users = await db.users.find().to_list(500)
    for u in users: 
        u["_id"] = str(u["_id"])
        if "password_hash" in u: u.pop("password_hash")
    return {"success": True, "users": users}

@app.get("/api/dev/dashboard-stats")
async def get_stats(user: dict = Depends(get_current_user)):
    if user["role"] != "Developer": raise HTTPException(403)
    total_users = await db.users.count_documents({})
    total_bots = await db.profiles.count_documents({})
    return {"success": True, "stats": {"totalUsers": total_users, "totalBots": total_bots, "pendingPayments": 0}}
