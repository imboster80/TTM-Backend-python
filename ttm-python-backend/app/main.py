from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import db # သင့် database အချိတ်အဆက်

app = FastAPI()

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. JSON Response Consistency (Error Handling)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": str(exc)},
    )

# 3. Trailing Slashes (ဥပမာ)
@app.post("/api/auth/login") 
async def login():
    # သင့် logic
    return {"success": True, "data": "Login successful"}
