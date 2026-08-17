from fastapi import APIRouter, Header, HTTPException

from app.firebase import db


router = APIRouter(
    prefix="/student",
    tags=["Student"]
)


@router.get("/me")
def get_student_me(
    student_token: str | None = Header(default=None)
):

    if not student_token:
        raise HTTPException(
            status_code=401,
            detail="학생 인증 토큰이 없습니다."
        )

    students = (
        db.collection("students")
        .where("studentToken", "==", student_token)
        .limit(1)
        .stream()
    )

    student_docs = list(students)

    if not student_docs:
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 학생 토큰입니다."
        )

    student_doc = student_docs[0]
    student_data = student_doc.to_dict()

    return {
        "success": True,
        "studentId": student_doc.id,
        "classId": student_data.get("classId"),
        "nickname": student_data.get("nickname"),
        "xp": student_data.get("xp", 0),
        "level": student_data.get("level", 1),
        "loginCount": student_data.get("loginCount", 0),
        "badge": student_data.get("badge", None)
    }