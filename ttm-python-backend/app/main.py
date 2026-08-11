from fastapi import FastAPI, Request, HTTPException, Depends, Header, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import jwt
import datetime
import bcrypt
from bson import ObjectId
from app.database import db
from app.utils import solve_image_ocr

app = FastAPI()

# Config
JWT_SECRET = "super_secret_jwt_key_123"
HARDCODED_DEV_TOKEN = "ttm_master_dev_token_2026"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "User"

class ProfileModel(BaseModel):
    profile_name: str
    bot_token: str
    admin_id: str

class RedeemCreateRequest(BaseModel):
    code: str
    hours: float
    max_uses: int

# --- Auth Helper ---
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    
    token = authorization.split(" ")[1] if " " in authorization else authorization
    
    if token == HARDCODED_DEV_TOKEN:
        return {"_id": "000000000000000000000000", "username": "MasterDeveloper", "role": "Developer"}

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = await db.User.find_one({"_id": ObjectId(payload["id"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid Token")

# --- Endpoints ---

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    existing = await db.User.find_one({"username": req.username})
    if existing:
        return {"success": False, "detail": "Username already exists"}
    
    hashed = bcrypt.hashpw(req.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = {
        "username": req.username,
        "password_hash": hashed,
        "role": req.role,
        "vip_expiry": None,
        "is_banned": False,
        "created_at": datetime.datetime.utcnow()
    }
    await db.User.insert_one(new_user)
    return {"success": True, "message": "Registered successfully"}

@app.post("/api/auth/login")

