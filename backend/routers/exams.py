import json
from fastapi import APIRouter, HTTPException, Depends
from schemas import ExamCreate, StatusChange
from auth import require_admin
from db import get_conn

router = APIRouter()


# POST /api/exams — 시험 생성
@router.post("/exams", status_code=201)
async def create_exam(body: ExamCreate, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute(
            "INSERT INTO exams (title, duration, source_text, created_by) VALUES (%s, %s, %s, %s)",
            (body.title, body.duration, body.source_text, user["id"]),
        )
        exam_id = cur.lastrowid
        await cur.execute(
            "SELECT id, title, duration, status, created_at FROM exams WHERE id = %s",
            (exam_id,),
        )
        exam = await cur.fetchone()
    return exam


# GET /api/exams — 시험 목록 조회 (문항 수 포함)
@router.get("/exams")
async def list_exams(user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute(
            """SELECT e.id, e.title, e.duration, e.status, e.created_at,
                      COUNT(q.id) AS question_count
                 FROM exams e
            LEFT JOIN questions q ON q.exam_id = e.id
             GROUP BY e.id
             ORDER BY e.created_at DESC"""
        )
        rows = await cur.fetchall()
    return rows


# GET /api/exams/{exam_id} — 시험 상세 (문제 포함, 정답/해설 포함)
@router.get("/exams/{exam_id}")
async def get_exam(exam_id: int, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id, title, duration, source_text, status, created_at FROM exams WHERE id = %s",
            (exam_id,),
        )
        exam = await cur.fetchone()
        if not exam:
            raise HTTPException(404, "exam not found")

        await cur.execute(
            """SELECT id, number, type, text, options, answer, explanation
                 FROM questions WHERE exam_id = %s ORDER BY number""",
            (exam_id,),
        )
        questions = await cur.fetchall()

    # JSON 컬럼 파싱
    for q in questions:
        if q["options"] and isinstance(q["options"], str):
            q["options"] = json.loads(q["options"])

    exam["questions"] = questions
    return exam


# PATCH /api/exams/{exam_id} — 시험 제목/설정 변경
@router.patch("/exams/{exam_id}")
async def update_exam(exam_id: int, body: dict, user: dict = Depends(require_admin)):
    allowed = {"title", "duration"}
    updates = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not updates:
        raise HTTPException(400, "nothing to update")
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM exams WHERE id = %s", (exam_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "exam not found")
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        await cur.execute(f"UPDATE exams SET {set_clause} WHERE id = %s", (*updates.values(), exam_id))
        await cur.execute("SELECT id, title, duration, status FROM exams WHERE id = %s", (exam_id,))
        return await cur.fetchone()


# PATCH /api/exams/{exam_id}/status — 상태 변경
@router.patch("/exams/{exam_id}/status")
async def change_status(exam_id: int, body: StatusChange, user: dict = Depends(require_admin)):
    if body.status not in ("ready", "active", "closed"):
        raise HTTPException(400, "status must be ready, active, or closed")

    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id, status FROM exams WHERE id = %s", (exam_id,))
        exam = await cur.fetchone()
        if not exam:
            raise HTTPException(404, "exam not found")

        await cur.execute(
            "UPDATE exams SET status = %s WHERE id = %s",
            (body.status, exam_id),
        )

    return {"id": exam_id, "status": body.status}


# DELETE /api/exams/{exam_id} — 삭제
@router.delete("/exams/{exam_id}", status_code=204)
async def delete_exam(exam_id: int, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM exams WHERE id = %s", (exam_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "exam not found")
        await cur.execute("DELETE FROM exams WHERE id = %s", (exam_id,))
    return None
