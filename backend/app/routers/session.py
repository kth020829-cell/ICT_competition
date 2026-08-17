from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from fastapi import UploadFile, File
from app.firebase import db


router = APIRouter(
    prefix="/sessions",
    tags=["Session"]
)


# ------------------------------------------
# Request Model
# ------------------------------------------

class SessionCreateRequest(BaseModel):
    type: str


# ------------------------------------------
# POST /sessions
# ------------------------------------------

@router.post("/{session_id}/before")
async def upload_before_image(
    session_id: str,
    file: UploadFile = File(...),
    student_token: str | None = Header(default=None)
):

    # ======================================
    # 1. 학생 인증
    # ======================================

    if not student_token:
        raise HTTPException(
            status_code=401,
            detail="학생 인증 토큰이 없습니다."
        )

    students = (
        db.collection("students")
        .where(
            "studentToken",
            "==",
            student_token
        )
        .limit(1)
        .stream()
    )

    student_docs = list(students)

    if not student_docs:
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 학생 토큰입니다."
        )

    student_id = student_docs[0].id


    # ======================================
    # 2. 세션 확인
    # ======================================

    session_ref = (
        db.collection("sessions")
        .document(session_id)
    )

    session_doc = session_ref.get()

    if not session_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 세션입니다."
        )

    session_data = session_doc.to_dict()


    # ======================================
    # 3. 세션 소유자 확인
    # ======================================

    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )


    # ======================================
    # 4. 세션 상태 확인
    # ======================================

    if session_data.get("status") != "CREATED":
        raise HTTPException(
            status_code=400,
            detail="사진을 업로드할 수 없는 세션입니다."
        )


    # ======================================
    # 5. 파일 형식 확인
    # ======================================

    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 이미지 형식입니다."
        )


    # ======================================
    # 6. 현재는 AI 연결 전이므로
    #    사진을 실제 분석하지 않고 테스트
    # ======================================

    image_data = await file.read()

    if len(image_data) == 0:
        raise HTTPException(
            status_code=400,
            detail="빈 이미지입니다."
        )


    # ======================================
    # 7. 세션 상태 변경
    # ======================================

    session_ref.update({
        "status": "PROCESSING"
    })


    # ======================================
    # 8. 임시 응답
    # ======================================

    return {
        "success": True,
        "sessionId": session_id,
        "status": "PROCESSING",
        "message": "사진 업로드 성공"
    }