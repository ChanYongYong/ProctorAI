import json
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from schemas import QuestionCreate, QuestionGenerate, QuestionUpdate
from auth import require_admin
from db import get_conn
import httpx
from PyPDF2 import PdfReader
import io

router = APIRouter()


# POST /api/questions — 문제 수동 생성
@router.post("/questions", status_code=201)
async def create_question(body: QuestionCreate, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM exams WHERE id = %s", (body.exam_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "exam not found")

        await cur.execute(
            "SELECT COALESCE(MAX(number), 0) AS max_num FROM questions WHERE exam_id = %s",
            (body.exam_id,),
        )
        max_num = (await cur.fetchone())["max_num"]

        options_json = json.dumps(body.options, ensure_ascii=False) if body.options else None
        await cur.execute(
            """INSERT INTO questions (exam_id, number, type, text, options, answer, explanation)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (body.exam_id, max_num + 1, body.type, body.text, options_json, body.answer, body.explanation),
        )
        q_id = cur.lastrowid

        await cur.execute(
            "SELECT id, number, type, text, options, answer, explanation FROM questions WHERE id = %s",
            (q_id,),
        )
        q = await cur.fetchone()

    if q["options"] and isinstance(q["options"], str):
        q["options"] = json.loads(q["options"])
    return q


# POST /api/questions/extract-pdf — PDF 텍스트 추출
@router.post("/questions/extract-pdf")
async def extract_pdf(file: UploadFile = File(...), user: dict = Depends(require_admin)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF file required")

    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        text = ""
        for page in reader.pages[:20]:  # 최대 20페이지
            text += page.extract_text() or ""
            text += "\n"
        text = text.strip()
    except Exception as e:
        raise HTTPException(400, f"PDF parse error: {str(e)}")

    return {"text": text, "pages": len(reader.pages)}


# POST /api/questions/generate — AI 문제 생성
@router.post("/questions/generate", status_code=201)
async def generate_questions(body: QuestionGenerate, user: dict = Depends(require_admin)):
    # 시험 존재 확인
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM exams WHERE id = %s", (body.exam_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "exam not found")

    # Groq API 키 조회
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT groq_key FROM settings WHERE user_id = %s", (user["id"],)
        )
        row = await cur.fetchone()

    groq_key = row["groq_key"] if row and row["groq_key"] else None
    if not groq_key:
        raise HTTPException(400, "Groq API key not set. Go to settings first.")

    # 프롬프트 구성
    if body.type == "choice":
        format_desc = '{"questions":[{"question":"문제 내용","options":["① 보기1","② 보기2","③ 보기3","④ 보기4"],"answer":0,"explanation":"해설"}]}'
        type_desc = "4지선다 객관식"
    else:
        format_desc = '{"questions":[{"question":"문제 내용","answer":"모범답안","explanation":"해설"}]}'
        type_desc = "서술형"

    prompt = (
        f"다음 교육 자료를 분석하여 {type_desc} 문제 {body.count}개를 생성하세요.\n\n"
        f"교육 자료:\n{body.source_text[:5500]}\n\n"
        f"반드시 아래 JSON 형식으로만 응답 (다른 텍스트 없이):\n{format_desc}\n"
        f"answer는 정답 index(0~3). 반드시 한국어."
    )

    # Groq API 호출
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {groq_key}",
                },
                json={
                    "model": "llama3-8b-8192",
                    "max_tokens": 4000,
                    "temperature": 0.7,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if res.status_code != 200:
            raise HTTPException(502, f"Groq API error: {res.status_code}")

        data = res.json()
        raw = data["choices"][0]["message"]["content"].strip()
        # ```json ... ``` 제거
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        questions = parsed["questions"]
    except json.JSONDecodeError:
        raise HTTPException(502, "AI response is not valid JSON")
    except (KeyError, IndexError):
        raise HTTPException(502, "unexpected AI response format")
    except httpx.TimeoutException:
        raise HTTPException(504, "Groq API timeout")

    # DB에 문제 저장
    saved = []
    async with get_conn() as (conn, cur):
        # 기존 문제 번호 확인
        await cur.execute(
            "SELECT COALESCE(MAX(number), 0) AS max_num FROM questions WHERE exam_id = %s",
            (body.exam_id,),
        )
        max_num = (await cur.fetchone())["max_num"]

        for i, q in enumerate(questions):
            num = max_num + i + 1
            q_type = body.type
            q_text = q.get("question", "")
            q_options = json.dumps(q.get("options"), ensure_ascii=False) if q.get("options") else None
            q_answer = str(q.get("answer", ""))
            q_explanation = q.get("explanation", "")

            await cur.execute(
                """INSERT INTO questions (exam_id, number, type, text, options, answer, explanation)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (body.exam_id, num, q_type, q_text, q_options, q_answer, q_explanation),
            )
            saved.append({
                "id": cur.lastrowid,
                "number": num,
                "type": q_type,
                "text": q_text,
                "options": q.get("options"),
                "answer": q.get("answer"),
                "explanation": q_explanation,
            })

    return {"questions": saved}


# PUT /api/questions/{question_id} — 문제 수정
@router.put("/questions/{question_id}")
async def update_question(question_id: int, body: QuestionUpdate, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM questions WHERE id = %s", (question_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "question not found")

        updates = []
        params = []
        if body.text is not None:
            updates.append("text = %s")
            params.append(body.text)
        if body.options is not None:
            updates.append("options = %s")
            params.append(json.dumps(body.options, ensure_ascii=False))
        if body.answer is not None:
            updates.append("answer = %s")
            params.append(body.answer)
        if body.explanation is not None:
            updates.append("explanation = %s")
            params.append(body.explanation)

        if not updates:
            raise HTTPException(400, "nothing to update")

        params.append(question_id)
        await cur.execute(
            f"UPDATE questions SET {', '.join(updates)} WHERE id = %s", tuple(params)
        )

        await cur.execute(
            "SELECT id, number, type, text, options, answer, explanation FROM questions WHERE id = %s",
            (question_id,),
        )
        q = await cur.fetchone()

    if q["options"] and isinstance(q["options"], str):
        q["options"] = json.loads(q["options"])
    return q


# DELETE /api/questions/{question_id} — 문제 삭제
@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(question_id: int, user: dict = Depends(require_admin)):
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM questions WHERE id = %s", (question_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "question not found")
        await cur.execute("DELETE FROM questions WHERE id = %s", (question_id,))
    return None
