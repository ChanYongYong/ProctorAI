from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends
from jose import jwt, JWTError
from passlib.context import CryptContext
from db import get_conn

SECRET_KEY = "proctorai-secret-key-change-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain[:72], hashed)


def create_token(user_id: int, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "token required")
    token = auth[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "invalid token")

    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id, name, role FROM users WHERE id = %s", (user_id,))
        user = await cur.fetchone()
    if not user:
        raise HTTPException(401, "user not found")
    return user


async def require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "admin only")
    return user
