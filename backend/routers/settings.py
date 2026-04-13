from fastapi import APIRouter, Depends
from schemas import SettingsUpdate
from auth import require_admin, get_current_user
from db import get_conn

router = APIRouter()

DEFAULTS = {"groq_key": None, "gaze_threshold": 3, "max_warnings": 3}


# GET /api/admin/settings — 설정 조회
@router.get("/admin/settings")
async def get_settings(user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT groq_key, gaze_threshold, max_warnings FROM settings WHERE user_id = %s",
            (user["id"],),
        )
        row = await cur.fetchone()
    return row if row else DEFAULTS


# GET /api/student/groq-key — 학생용 Groq 키 조회 (인증된 모든 사용자)
@router.get("/student/groq-key")
async def get_groq_key(user: dict = Depends(get_current_user)):
    async with get_conn() as (conn, cur):
        # 관리자(admin role)의 설정에서 groq_key를 가져옴
        await cur.execute(
            "SELECT groq_key FROM settings s JOIN users u ON u.id = s.user_id WHERE u.role = 'admin' LIMIT 1"
        )
        row = await cur.fetchone()
    return {"groq_key": row["groq_key"] if row and row["groq_key"] else ""}


# PUT /api/admin/settings — 설정 저장
@router.put("/admin/settings")
async def save_settings(body: SettingsUpdate, user: dict = Depends(require_admin)):
    groq = body.groq_key
    gaze = body.gaze_threshold if body.gaze_threshold is not None else 3
    maxw = body.max_warnings if body.max_warnings is not None else 3

    async with get_conn() as (conn, cur):
        await cur.execute(
            """INSERT INTO settings (user_id, groq_key, gaze_threshold, max_warnings)
               VALUES (%s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE groq_key = %s, gaze_threshold = %s, max_warnings = %s""",
            (user["id"], groq, gaze, maxw, groq, gaze, maxw),
        )
        await cur.execute(
            "SELECT groq_key, gaze_threshold, max_warnings FROM settings WHERE user_id = %s",
            (user["id"],),
        )
        row = await cur.fetchone()
    return row
