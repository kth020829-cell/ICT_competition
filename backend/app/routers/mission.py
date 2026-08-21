from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app.firebase import db


router = APIRouter(
    prefix="/missions",
    tags=["Mission"]
)

def get_student(student_token: str | None):

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

    return student_docs[0]

@router.get("/today")
def get_today_mission(
    student_token: str | None = Header(default=None)
):

    student_doc = get_student(student_token)

    student_id = student_doc.id
    student_data = student_doc.to_dict()

    # ------------------------------------------
    # 오늘의 미션이 이미 배정되어 있는지 확인
    # ------------------------------------------

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    mission_data = student_data.get("todayMission")

    if mission_data:
        if mission_data.get("date") == today:

            mission_id = mission_data.get("missionId")

            mission_doc = (
                db.collection("missions")
                .document(mission_id)
                .get()
            )

            if mission_doc.exists:

                return {
                    "success": True,
                    "date": today,
                    "mission": {
                        "missionId": mission_doc.id,
                        **mission_doc.to_dict()
                    }
                }

    # ------------------------------------------
    # 활성화된 미션 가져오기
    # ------------------------------------------

    mission_docs = (
        db.collection("missions")
        .where(
            "active",
            "==",
            True
        )
        .stream()
    )

    missions = list(mission_docs)

    if not missions:
        raise HTTPException(
            status_code=404,
            detail="등록된 미션이 없습니다."
        )

    # ------------------------------------------
    # 랜덤 미션 선택
    # ------------------------------------------

    import random

    selected = random.choice(missions)

    mission_id = selected.id

    # ------------------------------------------
    # 학생에게 오늘의 미션 저장
    # ------------------------------------------

    db.collection("students").document(student_id).update({
        "todayMission": {
            "missionId": mission_id,
            "date": today,
            "completed": False
        }
    })

    # ------------------------------------------
    # 응답
    # ------------------------------------------

    return {
        "success": True,
        "date": today,
        "mission": {
            "missionId": mission_id,
            **selected.to_dict()
        }
    }

@router.get("/{mission_id}")
def get_mission(
    mission_id: str,
    student_token: str | None = Header(default=None)
):

    get_student(student_token)

    mission_doc = (
        db.collection("missions")
        .document(mission_id)
        .get()
    )

    if not mission_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 미션입니다."
        )

    return {
        "success": True,
        "mission": {
            "missionId": mission_doc.id,
            **mission_doc.to_dict()
        }
    }

@router.post("/{mission_id}/complete")
def complete_mission(
    mission_id: str,
    session_id: str,
    student_token: str | None = Header(default=None)
):

    # ==========================================
    # 1. 학생 인증
    # ==========================================

    student_doc = get_student(student_token)

    student_id = student_doc.id
    student_data = student_doc.to_dict()


    # ==========================================
    # 2. 미션 확인
    # ==========================================

    mission_ref = (
        db.collection("missions")
        .document(mission_id)
    )

    mission_doc = mission_ref.get()

    if not mission_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 미션입니다."
        )

    mission_data = mission_doc.to_dict()


    # ==========================================
    # 3. 오늘의 미션인지 확인
    # ==========================================

    today_mission = student_data.get(
        "todayMission"
    )

    if not today_mission:
        raise HTTPException(
            status_code=400,
            detail="오늘의 미션이 없습니다."
        )

    if today_mission.get("missionId") != mission_id:
        raise HTTPException(
            status_code=400,
            detail="현재 학생에게 배정된 미션이 아닙니다."
        )


    # ==========================================
    # 4. 이미 완료했는지 확인
    # ==========================================

    if today_mission.get("completed") is True:

        return {
            "success": True,
            "alreadyCompleted": True,
            "missionId": mission_id,
            "message": "이미 완료한 미션입니다."
        }


    # ==========================================
    # 5. 세션 확인
    # ==========================================

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


    # ==========================================
    # 6. 세션 소유자 확인
    # ==========================================

    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )


    # ==========================================
    # 7. 세션 완료 여부 확인
    # ==========================================

    if session_data.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료되지 않은 세션입니다."
        )


    # ==========================================
    # 8. 미션 완료 처리
    # ==========================================

    db.collection("students").document(student_id).update({
        "todayMission.completed": True
    })


    # ==========================================
    # 9. 세션에 미션 완료 기록
    # ==========================================

    session_ref.update({
        "missionId": mission_id,
        "missionCompleted": True,
        "missionBonusXp": 30
    })


    # ==========================================
    # 10. 응답
    # ==========================================

    return {
        "success": True,
        "alreadyCompleted": False,
        "missionId": mission_id,
        "sessionId": session_id,
        "completed": True,
        "bonusXp": 30,
        "message": "미션을 완료했습니다!"
    }