import json
from fastapi import APIRouter, HTTPException, Depends
from auth import get_current_user, require_admin
from db import get_conn

router = APIRouter()


async def _build_result(cur, attempt_id: int) -> dict:
    """attempt + answers + questions 조인하여 결과 빌드 (공통 로직)"""
    await cur.execute(
        """SELECT a.id AS attempt_id, a.status, a.score,
                  a.warning_count, a.total_away_time, a.voice_alerts,
                  a.started_at, a.submitted_at,
                  e.title AS exam_title,
                  u.name AS user_name
             FROM attempts a
             JOIN exams e ON a.exam_id = e.id
             JOIN users u ON a.user_id = u.id
            WHERE a.id = %s""",
        (attempt_id,),
    )
    attempt = await cur.fetchone()
    if not attempt:
        return None

    await cur.execute(
        """SELECT ans.question_id, ans.selected, ans.text AS answer_text, ans.is_correct,
                  q.number, q.type, q.text, q.options, q.answer AS correct_answer, q.explanation
             FROM answers ans
             JOIN questions q ON ans.question_id = q.id
            WHERE ans.attempt_id = %s
            ORDER BY q.number""",
        (attempt_id,),
    )
    answers = await cur.fetchall()

    for a in answers:
        if a["options"] and isinstance(a["options"], str):
            a["options"] = json.loads(a["options"])

    attempt["answers"] = answers
    return attempt


# GET /api/student/attempts/{attempt_id}/result — 내 결과 조회
@router.get("/student/attempts/{attempt_id}/result")
async def my_result(attempt_id: int, user: dict = Depends(get_current_user)):
    async with get_conn() as (conn, cur):
        # 본인 확인
        await cur.execute(
            "SELECT user_id FROM attempts WHERE id = %s", (attempt_id,)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "attempt not found")
        if row["user_id"] != user["id"]:
            raise HTTPException(403, "not your attempt")

        result = await _build_result(cur, attempt_id)
    return result


# GET /api/admin/attempts/{attempt_id}/result — 관리자 결과 조회
@router.get("/admin/attempts/{attempt_id}/result")
async def admin_result(attempt_id: int, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        result = await _build_result(cur, attempt_id)
    if not result:
        raise HTTPException(404, "attempt not found")
    return result


# GET /api/admin/exams/{exam_id}/results — 시험별 전체 결과 목록
@router.get("/admin/exams/{exam_id}/results")
async def exam_results(exam_id: int, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM exams WHERE id = %s", (exam_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "exam not found")

        await cur.execute(
            """SELECT a.id AS attempt_id, a.user_id, u.name AS user_name,
                      a.status, a.score, a.warning_count, a.total_away_time,
                      a.voice_alerts, a.started_at, a.submitted_at
                 FROM attempts a
                 JOIN users u ON a.user_id = u.id
                WHERE a.exam_id = %s
             ORDER BY a.started_at DESC""",
            (exam_id,),
        )
        rows = await cur.fetchall()
    return rows
