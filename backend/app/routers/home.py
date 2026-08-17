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
    # 3. 오늘의 미션
    # ==========================================

    today = datetime.now(timezone.utc).date().isoformat()

    today_mission_docs = list(
        db.collection("student_missions")
        .where("studentId", "==", student_id)
        .where("assignedDate", "==", today)
        .limit(1)
        .stream()
    )


    # 이미 오늘의 미션이 있는 경우
    if today_mission_docs:

        student_mission_doc = today_mission_docs[0]
        student_mission_data = student_mission_doc.to_dict()

        mission_id = student_mission_data.get("missionId")

        mission_doc = (
            db.collection("missions")
            .document(mission_id)
            .get()
        )

        if mission_doc.exists:

            mission_data = mission_doc.to_dict()

            today_mission = {
                "missionId": mission_doc.id,
                "title": mission_data.get("title"),
                "description": mission_data.get("description"),
                "type": mission_data.get("type"),
                "rewardXp": mission_data.get("rewardXp", 0),
                "completed": student_mission_data.get(
                    "completed",
                    False
                )
            }

        else:
            today_mission = None


    # 오늘의 미션이 없는 경우 → 랜덤 배정
    else:

        mission_docs = list(
            db.collection("missions")
            .where("active", "==", True)
            .stream()
        )

        if not mission_docs:

            today_mission = None

        else:

            selected_mission = random.choice(mission_docs)

            mission_id = selected_mission.id
            mission_data = selected_mission.to_dict()

            # 학생에게 오늘의 미션 저장
            db.collection("student_missions").document().set({
                "studentId": student_id,
                "missionId": mission_id,
                "assignedDate": today,
                "completed": False,
                "completedAt": None
            })

            today_mission = {
                "missionId": mission_id,
                "title": mission_data.get("title"),
                "description": mission_data.get("description"),
                "type": mission_data.get("type"),
                "rewardXp": mission_data.get("rewardXp", 0),
                "completed": False
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

    student_collection_docs = list(
        db.collection("student_collections")
        .where("studentId", "==", student_id)
        .stream()
    )

    collected_count = len(student_collection_docs)

    card_docs = list(
        db.collection("cards")
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
        "todayMission": today_mission,
        "classGoal": class_goal,
        "collection": collection
    }