from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import init_pool, close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="ProctorAI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# 라우터 등록
from routers import auth as auth_router
from routers import exams as exams_router
from routers import questions as questions_router
from routers import student as student_router
from routers import results as results_router
from routers import settings as settings_router
from routers import proctoring as proctoring_router
from routers import monitor as monitor_router
from routers import clarifications as clarifications_router
from routers import groq_proxy as groq_proxy_router

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(exams_router.router, prefix="/api", tags=["exams"])
app.include_router(questions_router.router, prefix="/api", tags=["questions"])
app.include_router(student_router.router, prefix="/api/student", tags=["student"])
app.include_router(results_router.router, prefix="/api", tags=["results"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(proctoring_router.router, prefix="/api/student", tags=["proctoring"])
app.include_router(monitor_router.router, prefix="/api", tags=["monitor"])
app.include_router(clarifications_router.router, prefix="/api", tags=["clarifications"])
app.include_router(groq_proxy_router.router, prefix="/api", tags=["groq"])
