from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.student import router as student_router
from app.routers.home import router as home_router
from app.routers.session import router as session_router
from app.routers.reward import router as reward_router
from app.routers.mission import router as mission_router

app = FastAPI()


app.include_router(auth_router)
app.include_router(student_router)
app.include_router(home_router)
app.include_router(session_router)
app.include_router(reward_router)
app.include_router(mission_router)

@app.get("/")
def root():
    return {"message": "Hello"}