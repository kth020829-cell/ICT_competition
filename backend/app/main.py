from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.student import router as student_router
from app.routers.home import router as home_router
from app.routers.session import router as session_router
from app.routers.reward import router as reward_router
from app.routers.mission import router as mission_router
from app.routers.collection import router as collection_router
from app.routers.teacher import router as teacher_router

app = FastAPI()

# 프론트엔드(vinext dev = :3000)가 브라우저에서 직접 호출한다.
# 이게 없으면 preflight가 405로 떨어져 모든 요청이 차단된다.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(student_router)
app.include_router(home_router)
app.include_router(session_router)
app.include_router(reward_router)
app.include_router(mission_router)
app.include_router(collection_router)
app.include_router(teacher_router)

@app.get("/")
def root():
    return {"message": "Hello"}