import secrets

from fastapi import APIRouter, HTTPException

from app.firebase import db
from app.schemas.auth import StudentJoinRequest
from google.cloud.firestore_v1 import Increment


router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post("/student")
def student_join(request: StudentJoinRequest):

    # 1. 학급 코드로 학급 검색
    classes = (
        db.collection("classes")
        .where("classCode", "==", request.classCode)
        .limit(1)
        .stream()
    )

    class_docs = list(classes)

    if not class_docs:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 학급 코드입니다."
        )

    class_doc = class_docs[0]
    class_data = class_doc.to_dict()
    class_id = class_doc.id

    # 2. 학급 잠금 확인
    if class_data.get("locked", False):
        raise HTTPException(
            status_code=403,
            detail="현재 잠긴 학급입니다."
        )

    # 3. 닉네임 중복 확인
    students = (
        db.collection("students")
        .where("classId", "==", class_id)
        .where("nickname", "==", request.nickname)
        .limit(1)
        .stream()
    )

    if any(students):
        raise HTTPException(
            status_code=409,
            detail="이미 사용 중인 닉네임입니다."
        )

    # 4. 익명 토큰 생성
    student_token = secrets.token_urlsafe(32)

    # 5. 학생 문서 생성
    student_ref = db.collection("students").document()
    class_ref = db.collection("classes").document(class_id)

    student_ref.set({
        "classId": class_id,
        "nickname": request.nickname,
        "studentToken": student_token,
        "xp": 0,
        "level": 1,
        "badge": "bronze"
    })

    class_ref.update({
        "studentCount": Increment(1)
    })

    # 6. 응답
    return {
        "success": True,
        "studentId": student_ref.id,
        "studentToken": student_token,
        "nickname": request.nickname,
        "classId": class_id
    }