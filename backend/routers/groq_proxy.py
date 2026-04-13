from fastapi import APIRouter, HTTPException, Depends
from auth import get_current_user
from db import get_conn
import httpx

router = APIRouter()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def _get_groq_key():
    """DB에서 관리자 Groq 키 조회"""
    async with get_conn() as (conn, cur):
        await cur.execute(
            """SELECT s.groq_key FROM settings s
               JOIN users u ON u.id = s.user_id
               WHERE u.role = 'admin' LIMIT 1"""
        )
        row = await cur.fetchone()
    return row["groq_key"] if row and row.get("groq_key") else None


# POST /api/student/groq/chat — AI 면담 챗봇 프록시 (키 서버사이드 보관)
@router.post("/student/groq/chat")
async def groq_chat(body: dict, user: dict = Depends(get_current_user)):
    key = await _get_groq_key()
    if not key:
        raise HTTPException(400, "Groq API key not configured")

    system_msg = body.get("system", "")
    messages = body.get("messages", [])
    model = body.get("model", "llama-3.1-8b-instant")
    max_tokens = body.get("max_tokens", 250)
    temperature = body.get("temperature", 0.7)

    payload_messages = []
    if system_msg:
        payload_messages.append({"role": "system", "content": system_msg})
    payload_messages.extend(messages)

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": payload_messages,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if not res.is_success:
            raise HTTPException(502, f"Groq API error: {res.status_code}")
        return res.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "Groq API timeout")
