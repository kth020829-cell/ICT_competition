from datetime import datetime, timezone
import random

from fastapi import APIRouter, Header, HTTPException

from app.firebase import db


router = APIRouter(
    prefix="/student",
    tags=["Home"]
)


@router.get("/home")
def get_student_home(
    student_token: str | None = Header(default=None)
):

    # ==========================================
    # 1. 학생 인증
    # ==========================================

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

    student_id = student_doc.id
    class_id = student_data.get("classId")


    # ==========================================
    # 2. 학생 정보
    # ==========================================

    student = {
        "studentId": student_id,
        "nickname": student_data.get("nickname"),
        "level": student_data.get("level", 1),
        "xp": student_data.get("xp", 0),
        "loginCount": student_data.get("LoginCount", 0),
        "badge": student_data.get("badge")
    }




    # ==========================================
    # 4. 학급 목표
    # ==========================================

    class_doc = (
        db.collection("classes")
        .document(class_id)
        .get()
    )

    if class_doc.exists:

        class_data = class_doc.to_dict()

        current = class_data.get("goalCurrent", 0)
        target = class_data.get("goalTarget", 0)

        if target > 0:
            progress = current / target
        else:
            progress = 0

        progress = min(progress, 1)

        class_goal = {
            "current": current,
            "target": target,
            "progress": progress
        }

    else:

        class_goal = {
            "current": 0,
            "target": 0,
            "progress": 0
        }


    # ==========================================
    # 5. 도감 수집 상태
    # ==========================================

    # 카드는 students/{id}/collection 서브컬렉션에 쌓인다.
    # (app/services/collection.py 가 거기에 쓰고, /collection 도 거기서 읽는다)
    # 예전에는 존재하지 않는 최상위 student_collections 를 읽어서
    # 홈의 도감 개수가 항상 0으로 나왔다.
    student_collection_docs = list(
        db.collection("students")
        .document(student_id)
        .collection("collection")
        .stream()
    )

    collected_count = len(student_collection_docs)

    card_docs = list(
        db.collection("card")
        .stream()
    )

    total_count = len(card_docs)

    collection = {
        "collected": collected_count,
        "total": total_count
    }


    # ==========================================
    # 6. 최종 응답
    # ==========================================

    return {
        "success": True,
        "student": student,
        "classGoal": class_goal,
        "collection": collection
    }