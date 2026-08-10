import os
import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Header, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt

from app.database import db
from app.utils import solve_image_ocr

app = FastAPI(title="TTM Backend Python Server")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_123")
HARDCODED_DEV_TOKEN = os.getenv("HARDCODED_DEV_TOKEN", "ttm_master_dev_token_2026")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


# ==========================================
# PYDANTIC MODELS
# ==========================================
class RegisterModel(BaseModel):
    username: str
    password: str
    role: Optional[str] = "User"

class LoginModel(BaseModel):
    username: str
    password: str

class BotProfileModel(BaseModel):
    profile_name: str
    bot_token: str
    admin_id: str

class UserRedeemModel(BaseModel):
    code: str


# ==========================================
# AUTHENTICATION & ROLES
# ==========================================
async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    token = credentials.credentials
    if token == HARDCODED_DEV_TOKEN:
        return {
            "id": "000000000000000000000000",
            "username": "MasterDeveloper",
            "role": "Developer"
        }
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid or expired token")

def verify_role(required_roles: List[str]):
    def role_dependency(user: dict = Depends(verify_token)):
        if user.get("role") not in required_roles:
            raise HTTPException(status_code=403, detail="Permission denied: Insufficient role")
        return user
    return role_dependency


# ==========================================
# API ROUTES
# ==========================================
@app.post("/api/auth/register")
async def register(data: RegisterModel):
    existing = await db.users.find_one({"username": data.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    assigned_role = data.role if data.role in ["User", "Admin"] else "User"
    hashed_password = pwd_context.hash(data.password)

    new_user = {
        "username": data.username,
        "password_hash": hashed_password,
        "role": assigned_role,
        "vip_expiry": None,
        "is_banned": False,
        "created_at": datetime.datetime.utcnow()
    }
    await db.users.insert_one(new_user)
    return {"success": True, "message": f"Account registered successfully as {assigned_role}"}

@app.post("/api/auth/login")
async def login(data: LoginModel):
    user = await db.users.find_one({"username": data.username})
    if not user or user.get("is_banned"):
        raise HTTPException(status_code=400, detail="Invalid credentials or user banned")
    
    if not pwd_context.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    token_payload = {
        "id": str(user["_id"]),
        "username": user["username"],
        "role": user["role"]
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")
    return {"success": True, "token": token, "role": user["role"]}

@app.get("/api/auth/me")
async def get_me(user_info: dict = Depends(verify_token)):
    if user_info["id"] == "000000000000000000000000":
        return {
            "success": True,
            "user": {
                "_id": "000000000000000000000000",
                "username": "MasterDeveloper",
                "role": "Developer",
                "vip_expiry": None,
                "isVip": True,
                "is_banned": False,
                "created_at": datetime.datetime.utcnow()
            }
        }
    
    from bson import ObjectId
    user = await db.users.find_one({"_id": ObjectId(user_info["id"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    now = datetime.datetime.utcnow()
    vip_expiry = user.get("vip_expiry")
    is_vip = vip_expiry and vip_expiry > now

    return {
        "success": True,
        "user": {
            "_id": str(user["_id"]),
            "username": user["username"],
            "role": user["role"],
            "vip_expiry": vip_expiry,
            "isVip": is_vip,
            "is_banned": user.get("is_banned", False),
            "created_at": user.get("created_at")
        }
    }

@app.get("/api/profiles")
async def get_profiles(user: dict = Depends(verify_token)):
    profiles = await db.botprofiles.find({"user_id": user["id"]}).to_list(100)
    for p in profiles:
        p["_id"] = str(p["_id"])
    return {"success": True, "profiles": profiles}

@app.post("/api/profiles")
async def create_profile(data: BotProfileModel, user: dict = Depends(verify_token)):
    new_profile = {
        "user_id": user["id"],
        "profile_name": data.profile_name,
        "bot_token": data.bot_token,
        "admin_id": data.admin_id
    }
    result = await db.botprofiles.insert_one(new_profile)
    new_profile["_id"] = str(result.inserted_id)
    return {"success": True, "message": "Bot profile saved", "profile": new_profile}

@app.post("/api/utils/solve-captcha")
async def solve_captcha(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        res = solve_image_ocr(contents)
        return {"success": True, "message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment/upload")
async def upload_payment(
    transaction_id: str = Form(...),
    amount: float = Form(...),
    screenshot: UploadFile = File(...),
    user: dict = Depends(verify_token)
):
    try:
        image_bytes = await screenshot.read()
        ocr_text = solve_image_ocr(image_bytes)

        payment_doc = {
            "user_id": user["id"],
            "transaction_id": transaction_id,
            "amount": amount,
            "screenshot_url": screenshot.filename,
            "ocr_text": ocr_text,
            "status": "pending",
            "created_at": datetime.datetime.utcnow()
        }
        result = await db.payments.insert_one(payment_doc)
        return {
            "success": True,
            "message": "Payment uploaded and OCR processed successfully",
            "orderId": str(result.inserted_id),
            "ocrText": ocr_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user/codes/redeem")
async def redeem_code(data: UserRedeemModel, user: dict = Depends(verify_token)):
    code_doc = await db.redeemcodes.find_one({"code": data.code})
    if not code_doc or code_doc["used_count"] >= code_doc["max_uses"]:
        raise HTTPException(status_code=400, detail="Invalid or fully used redeem code")
    
    from bson import ObjectId
    db_user = await db.users.find_one({"_id": ObjectId(user["id"])})
    now = datetime.datetime.utcnow()
    current_expiry = db_user.get("vip_expiry")
    if not current_expiry or current_expiry < now:
        current_expiry = now
    
    new_expiry = current_expiry + datetime.timedelta(hours=code_doc["hours"])

    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"vip_expiry": new_expiry}})
    await db.redeemcodes.update_one({"code": data.code}, {"$inc": {"used_count": 1}})

    return {"success": True, "message": f"Successfully redeemed {code_doc['hours']} VIP hours!"}

@app.get("/api/dev/dashboard-stats")
async def dev_stats(user: dict = Depends(verify_role(["Developer"]))):
    total_users = await db.users.count_documents({})
    total_bots = await db.botprofiles.count_documents({})
    pending_payments = await db.payments.count_documents({"status": "pending"})

    return {
        "success": True,
        "stats": {
            "totalUsers": total_users,
            "totalBots": total_bots,
            "pendingPayments": pending_payments
        }
    }

@app.get("/")
def root():
    return {"message": "TTM Python FastAPI Backend with ddddocr is running!"}