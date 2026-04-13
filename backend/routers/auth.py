from fastapi import APIRouter, HTTPException, Depends
from schemas import RegisterRequest, LoginRequest, UserOut, LoginResponse
from auth import hash_password, verify_password, create_token, get_current_user, require_admin
from db import get_conn

router = APIRouter()


# POST /api/auth/register — 회원가입
@router.post("/register", status_code=201)
async def register(body: RegisterRequest):
    if body.role not in ("admin", "student"):
        raise HTTPException(400, "role must be admin or student")

    async with get_conn() as (conn, cur):
        # 이름 중복 체크
        await cur.execute("SELECT id FROM users WHERE name = %s", (body.name,))
        if await cur.fetchone():
            raise HTTPException(400, "name already exists")

        hashed = hash_password(body.password)
        await cur.execute(
            "INSERT INTO users (name, password_hash, role) VALUES (%s, %s, %s)",
            (body.name, hashed, body.role),
        )
        user_id = cur.lastrowid

    return {"id": user_id, "name": body.name, "role": body.role}


# POST /api/auth/login — 로그인
@router.post("/login")
async def login(body: LoginRequest):
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id, name, password_hash, role FROM users WHERE name = %s",
            (body.name,),
        )
        user = await cur.fetchone()

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "invalid name or password")

    token = create_token(user["id"], user["role"])
    return {
        "token": token,
        "user": {"id": user["id"], "name": user["name"], "role": user["role"]},
    }


# GET /api/auth/me — 내 정보 조회
@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "name": user["name"], "role": user["role"]}


# GET /api/auth/users — 전체 사용자 목록 (관리자)
@router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id, name, role, created_at FROM users ORDER BY id")
        rows = await cur.fetchall()
    return rows


# PATCH /api/auth/users/{user_id}/name — 사용자 이름 변경 (관리자)
@router.patch("/users/{user_id}/name")
async def rename_user(user_id: int, body: dict, user: dict = Depends(require_admin)):
    new_name = body.get("name", "").strip()
    if not new_name:
        raise HTTPException(400, "name required")
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "user not found")
        await cur.execute("SELECT id FROM users WHERE name = %s AND id != %s", (new_name, user_id))
        if await cur.fetchone():
            raise HTTPException(400, "name already exists")
        await cur.execute("UPDATE users SET name = %s WHERE id = %s", (new_name, user_id))
    return {"id": user_id, "name": new_name}


# PATCH /api/auth/users/{user_id}/password — 비밀번호 변경 (관리자)
@router.patch("/users/{user_id}/password")
async def change_password(user_id: int, body: dict, user: dict = Depends(require_admin)):
    new_pw = body.get("password", "").strip()
    if not new_pw:
        raise HTTPException(400, "password required")
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "user not found")
        await cur.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                          (hash_password(new_pw), user_id))
    return {"id": user_id, "updated": True}
