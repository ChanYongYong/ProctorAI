from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from schemas import AttemptStatusChange
from auth import require_admin
from db import get_conn
import io

router = APIRouter()


# GET /api/admin/monitor/live — 실시간 응시자 현황
@router.get("/admin/monitor/live")
async def live_students(user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute(
            """SELECT a.id AS attempt_id, a.user_id, u.name AS user_name,
                      a.exam_id, e.title AS exam_title,
                      a.status, a.warning_count, a.started_at,
                      pl.event AS last_event, pl.severity AS last_severity,
                      pl.timestamp AS last_timestamp
                 FROM attempts a
                 JOIN users u ON a.user_id = u.id
                 JOIN exams e ON a.exam_id = e.id
            LEFT JOIN proctoring_logs pl ON pl.id = (
                      SELECT id FROM proctoring_logs
                       WHERE attempt_id = a.id
                    ORDER BY timestamp DESC LIMIT 1
                  )
                WHERE a.status = 'in_progress'
             ORDER BY a.started_at DESC"""
        )
        rows = await cur.fetchall()
    return rows


# PATCH /api/admin/attempts/{attempt_id}/status — attempt 상태 변경
@router.patch("/admin/attempts/{attempt_id}/status")
async def change_attempt_status(attempt_id: int, body: AttemptStatusChange, user: dict = Depends(require_admin)):
    valid = ("in_progress", "under_review", "submitted", "terminated")
    if body.status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")

    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id, status FROM attempts WHERE id = %s", (attempt_id,))
        attempt = await cur.fetchone()
        if not attempt:
            raise HTTPException(404, "attempt not found")

        await cur.execute(
            "UPDATE attempts SET status = %s WHERE id = %s",
            (body.status, attempt_id),
        )

    return {"attempt_id": attempt_id, "old_status": attempt["status"], "new_status": body.status}


# GET /api/admin/attempts/{attempt_id}/logs — 응시자별 로그 조회
@router.get("/admin/attempts/{attempt_id}/logs")
async def attempt_logs(attempt_id: int, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id FROM attempts WHERE id = %s", (attempt_id,)
        )
        if not await cur.fetchone():
            raise HTTPException(404, "attempt not found")

        await cur.execute(
            """SELECT id, severity, event, detail, timestamp
                 FROM proctoring_logs
                WHERE attempt_id = %s
             ORDER BY timestamp DESC""",
            (attempt_id,),
        )
        rows = await cur.fetchall()
    return rows


# GET /api/admin/logs — 전체 로그 조회 (필터 + 페이지네이션)
@router.get("/admin/logs")
async def all_logs(
    exam_id: int = Query(None),
    severity: str = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_admin),
):
    where = []
    params = []
    if exam_id:
        where.append("a.exam_id = %s")
        params.append(exam_id)
    if severity:
        where.append("pl.severity = %s")
        params.append(severity)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * size

    async with get_conn() as (conn, cur):
        # 총 건수
        await cur.execute(
            f"""SELECT COUNT(*) AS total
                  FROM proctoring_logs pl
                  JOIN attempts a ON pl.attempt_id = a.id
                  {where_sql}""",
            tuple(params),
        )
        total = (await cur.fetchone())["total"]

        # 데이터
        await cur.execute(
            f"""SELECT pl.id, pl.attempt_id, pl.severity, pl.event, pl.detail, pl.timestamp,
                       u.name AS user_name, e.title AS exam_title
                  FROM proctoring_logs pl
                  JOIN attempts a ON pl.attempt_id = a.id
                  JOIN users u ON a.user_id = u.id
                  JOIN exams e ON a.exam_id = e.id
                  {where_sql}
              ORDER BY pl.timestamp DESC
                 LIMIT %s OFFSET %s""",
            tuple(params) + (size, offset),
        )
        logs = await cur.fetchall()

    return {"total": total, "page": page, "size": size, "logs": logs}


# GET /api/admin/logs/export — CSV 내보내기
@router.get("/admin/logs/export")
async def export_csv(
    exam_id: int = Query(None),
    severity: str = Query(None),
    user: dict = Depends(require_admin),
):
    where = []
    params = []
    if exam_id:
        where.append("a.exam_id = %s")
        params.append(exam_id)
    if severity:
        where.append("pl.severity = %s")
        params.append(severity)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    async with get_conn() as (conn, cur):
        await cur.execute(
            f"""SELECT pl.timestamp, u.name AS user_name, e.title AS exam_title,
                       pl.event, pl.detail, pl.severity
                  FROM proctoring_logs pl
                  JOIN attempts a ON pl.attempt_id = a.id
                  JOIN users u ON a.user_id = u.id
                  JOIN exams e ON a.exam_id = e.id
                  {where_sql}
              ORDER BY pl.timestamp DESC""",
            tuple(params),
        )
        rows = await cur.fetchall()

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM for Excel
    buf.write("시각,응시자,시험,이벤트,내용,등급\n")
    for r in rows:
        ts = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if r["timestamp"] else ""
        detail = str(r["detail"] or "").replace('"', '""')
        buf.write(f'{ts},{r["user_name"]},{r["exam_title"]},{r["event"]},"{detail}",{r["severity"]}\n')

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=proctor_logs.csv"},
    )
