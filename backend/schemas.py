from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── 인증 ──

class RegisterRequest(BaseModel):
    name: str
    password: str
    role: str = "student"

class LoginRequest(BaseModel):
    name: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    role: str

class LoginResponse(BaseModel):
    token: str
    user: UserOut


# ── 시험 ──

class ExamCreate(BaseModel):
    title: str
    duration: int
    source_text: Optional[str] = None

class StatusChange(BaseModel):
    status: str


# ── 문제 ──

class QuestionGenerate(BaseModel):
    exam_id: int
    source_text: str
    count: int = 10
    type: str = "choice"

class QuestionCreate(BaseModel):
    exam_id: int
    type: str = "choice"
    text: str
    options: Optional[list] = None
    answer: str
    explanation: Optional[str] = None

class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    options: Optional[list] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None


# ── 학생 응시 ──

class AnswerItem(BaseModel):
    question_id: int
    selected: Optional[int] = None
    text: Optional[str] = None

class SubmitRequest(BaseModel):
    answers: List[AnswerItem]


# ── 감독 로그 ──

class LogCreate(BaseModel):
    severity: str
    event: str
    detail: str = ""

class EndExamRequest(BaseModel):
    warning_count: int = 0
    total_away_time: int = 0
    voice_alerts: int = 0


# ── 설정 ──

class SettingsUpdate(BaseModel):
    groq_key: Optional[str] = None
    gaze_threshold: Optional[int] = None
    max_warnings: Optional[int] = None


# ── 소명 ──

class ClarificationCreate(BaseModel):
    attempt_id: int
    reason_type: str
    reason_detail: str
    student_message: str

class DecisionRequest(BaseModel):
    status: str
    teacher_comment: Optional[str] = None


# ── 관리자 상태 변경 ──

class AttemptStatusChange(BaseModel):
    status: str
