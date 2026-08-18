import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from fastapi import UploadFile, File
from pydantic import BaseModel

from app.firebase import db


router = APIRouter(
    prefix="/sessions",
    tags=["Session"]
)


# ==========================================
# Request Models
# ==========================================

class SessionCreateRequest(BaseModel):
    type: str


class SessionResultRequest(BaseModel):
    detectedClass: str
    confidence: float
    needsAction: bool
    actions: list[str]
    disposalCategory: str
    feedbackText: str

class SessionAfterRequest(BaseModel):
    improved: bool


# ==========================================
# POST /sessions
# 세션 생성
# ==========================================

@router.post("")
def create_session(
    request: SessionCreateRequest,
    student_token: str | None = Header(default=None)
):

    # 1. 학생 인증
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

    # 2. 세션 타입 확인
    if request.type not in ["FREE", "MISSION"]:
        raise HTTPException(
            status_code=400,
            detail="세션 타입은 FREE 또는 MISSION이어야 합니다."
        )

    # 3. sessionId 생성
    session_id = str(uuid.uuid4())

    # 4. 세션 저장
    session_data = {
        "studentId": student_id,
        "type": request.type,
        "status": "CREATED",
        "createdAt": datetime.now(timezone.utc),
        "completedAt": None
    }

    db.collection("sessions").document(session_id).set(
        session_data
    )

    # 5. 응답
    return {
        "success": True,
        "sessionId": session_id,
        "type": request.type,
        "status": "CREATED"
    }


# ==========================================
# POST /sessions/{session_id}/before
# Before 사진 업로드
# ==========================================

@router.post("/{session_id}/before")
async def upload_before_image(
    session_id: str,
    file: UploadFile = File(...),
    student_token: str | None = Header(default=None)
):

    # 1. 학생 인증
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

    # 2. 세션 확인
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

    # 3. 세션 소유자 확인
    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )

    # 4. 세션 상태 확인
    if session_data.get("status") != "CREATED":
        raise HTTPException(
            status_code=400,
            detail="사진을 업로드할 수 없는 세션입니다."
        )

    # 5. 파일 형식 확인
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

    # 6. 이미지 읽기
    image_data = await file.read()

    if len(image_data) == 0:
        raise HTTPException(
            status_code=400,
            detail="빈 이미지입니다."
        )

    # 7. AI 처리 중 상태로 변경
    session_ref.update({
        "status": "PROCESSING"
    })

    # 8. 임시 응답
    return {
        "success": True,
        "sessionId": session_id,
        "status": "PROCESSING",
        "message": "사진 업로드 성공"
    }


# ==========================================
# POST /sessions/{session_id}/result
# AI 판정 결과 저장
# ==========================================

@router.post("/{session_id}/result")
def save_session_result(
    session_id: str,
    request: SessionResultRequest,
    student_token: str | None = Header(default=None)
):

    # 1. 학생 인증
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

    # 2. 세션 확인
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

    # 3. 세션 소유자 확인
    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )

    # 4. 세션 상태 확인
    if session_data.get("status") != "PROCESSING":
        raise HTTPException(
            status_code=400,
            detail="판정 결과를 저장할 수 없는 세션입니다."
        )

    # 5. 판정 결과 생성
    result_data = {
        "detectedClass": request.detectedClass,
        "confidence": request.confidence,
        "needsAction": request.needsAction,
        "actions": request.actions,
        "disposalCategory": request.disposalCategory,
        "feedbackText": request.feedbackText
    }

    # 6. 최종 상태 결정
    if request.needsAction:
        status = "ACTION_REQUIRED"
    else:
        status = "COMPLETED"

    # 7. Firestore에 한 번에 저장
    session_ref.update({
        "result": result_data,
        "status": status
    })

    # 8. 응답
    return {
        "success": True,
        "sessionId": session_id,
        "status": status,
        "result": result_data
    }



# ==========================================
# POST /sessions/{session_id}/after
# After 결과 저장
# ==========================================

@router.post("/{session_id}/after")
def save_after_result(
    session_id: str,
    request: SessionAfterRequest,
    student_token: str | None = Header(default=None)
):

    # 1. 학생 인증
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

    # 2. 세션 확인
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

    # 3. 세션 소유자 확인
    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )

    # 4. Action이 필요한 세션인지 확인
    if session_data.get("status") != "ACTION_REQUIRED":
        raise HTTPException(
            status_code=400,
            detail="After 촬영이 필요한 세션이 아닙니다."
        )

    # 5. After 결과 저장
    after_data = {
        "improved": request.improved
    }

    # 6. 개선 여부에 따른 상태 결정
    if request.improved:
        status = "COMPLETED"
    else:
        status = "ACTION_REQUIRED"

    # 7. Firestore 저장
    session_ref.update({
        "after": after_data,
        "status": status
    })

    # 8. 응답
    return {
        "success": True,
        "sessionId": session_id,
        "status": status,
        "improved": request.improved
    }