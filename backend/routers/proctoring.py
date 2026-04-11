from fastapi import APIRouter, HTTPException, Depends
from schemas import LogCreate, EndExamRequest
from auth import get_current_user
from db import get_conn

router = APIRouter()


# POST /api/student/attempts/{attempt_id}/logs — 감독 로그 전송
@router.post("/attempts/{attempt_id}/logs", status_code=201)
async def send_log(attempt_id: int, body: LogCreate, user: dict = Depends(get_current_user)):
    if body.severity not in ("ok", "info", "warn", "danger"):
        raise HTTPException(400, "severity must be ok, info, warn, or danger")

    async with get_conn() as (conn, cur):
        # attempt 확인
        await cur.execute(
            "SELECT id, user_id, status FROM attempts WHERE id = %s", (attempt_id,)
        )
        attempt = await cur.fetchone()
        if not attempt:
            raise HTTPException(404, "attempt not found")
        if attempt["user_id"] != user["id"]:
            raise HTTPException(403, "not your attempt")
        if attempt["status"] not in ("in_progress", "under_review"):
            raise HTTPException(400, "attempt already finished")

        # 로그 insert
        await cur.execute(
            """INSERT INTO proctoring_logs (attempt_id, severity, event, detail)
               VALUES (%s, %s, %s, %s)""",
            (attempt_id, body.severity, body.event, body.detail),
        )
        log_id = cur.lastrowid

        # warning 이벤트면 attempt의 warning_count 증가
        if body.event == "warning" or body.severity in ("warn", "danger"):
            await cur.execute(
                "UPDATE attempts SET warning_count = warning_count + 1 WHERE id = %s",
                (attempt_id,),
            )

        await cur.execute(
            "SELECT id, event, timestamp FROM proctoring_logs WHERE id = %s", (log_id,)
        )
        row = await cur.fetchone()

    return row


# POST /api/student/attempts/{attempt_id}/end — 시험 종료 (최종 통계 저장)
@router.post("/attempts/{attempt_id}/end")
async def end_exam(attempt_id: int, body: EndExamRequest, user: dict = Depends(get_current_user)):
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id, user_id, status FROM attempts WHERE id = %s", (attempt_id,)
        )
        attempt = await cur.fetchone()
        if not attempt:
            raise HTTPException(404, "attempt not found")
        if attempt["user_id"] != user["id"]:
            raise HTTPException(403, "not your attempt")
        if attempt["status"] != "in_progress":
            raise HTTPException(400, "attempt already finished")

        await cur.execute(
            """UPDATE attempts
               SET status = 'terminated',
                   warning_count = %s,
                   total_away_time = %s,
                   voice_alerts = %s,
                   submitted_at = NOW()
             WHERE id = %s""",
            (body.warning_count, body.total_away_time, body.voice_alerts, attempt_id),
        )

    return {"attempt_id": attempt_id, "status": "terminated"}
