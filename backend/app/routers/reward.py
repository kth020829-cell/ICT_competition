from fastapi import APIRouter, Header, HTTPException
from google.cloud.firestore_v1 import Increment

from app.firebase import db
from app.services.collection import collect_card
from app.services.mission import check_mission

router = APIRouter(
    prefix="/rewards",
    tags=["Reward"]
)

@router.post("/{session_id}")
def give_reward(
    session_id: str,
    student_token: str | None = Header(default=None)
):

    # ==========================================
    # 학생 인증
    # ==========================================

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

    student_doc = student_docs[0]

    student_id = student_doc.id

    student_data = student_doc.to_dict()

    # ==========================================
    # 세션 조회
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

    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="접근 권한이 없습니다."
        )

    if session_data.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료된 세션만 보상을 받을 수 있습니다."
        )

    # ==========================================
    # 중복 보상 방지
    # ==========================================

    reward_transaction_id = (
        f"{session_id}_reward"
    )

    reward_ref = (
        db.collection("rewardTransactions")
        .document(
            reward_transaction_id
        )
    )

    if reward_ref.get().exists:

        return {
            "success": True,
            "message": "이미 보상을 지급받았습니다."
        }

    # ==========================================
    # 오늘 미션 조회
    # ==========================================

    today_mission = student_data.get(
        "todayMission",
        {}
    )

    mission_id = today_mission.get(
        "todayMissionId"
    )

    mission_type = today_mission.get(
        "todayMissionType"
    )

    # ==========================================
    # 도감 자동 수집
    # ==========================================

    collection_result = {
        "registered": False,
        "cardId": None,
        "isNew": False,
        "count": 0
    }

    result_data = session_data.get(
        "result",
        {}
    )

    detected_class = result_data.get(
        "detectedClass"
    )

    if detected_class:

        collection_result = collect_card(
            student_id=student_id,
            detected_class=detected_class
        )

    # ==========================================
    # 미션 판정
    # ==========================================

    mission_completed = check_mission(
        mission_type=mission_type,
        session_data=session_data,
        collection_result=collection_result
    )

    # ==========================================
    # XP 계산
    # ==========================================

    xp_gain = 10

    if mission_completed:
        xp_gain += 30

    current_xp = student_data.get(
        "xp",
        0
    )

    new_xp = current_xp + xp_gain

    # ==========================================
    # 레벨 계산
    # 누적 XP 방식
    # ==========================================

    new_level = (
        new_xp // 50
    ) + 1

    # ==========================================
    # 뱃지 계산
    # ==========================================

    if new_level >= 20:

        badge = "CHALLENGER"

    elif new_level >= 5:

        badge = "GOLD"

    elif new_level >= 2:

        badge = "SILVER"

    else:

        badge = "BRONZE"

    # ==========================================
    # 학생 업데이트
    # ==========================================

    student_ref = (
        db.collection("students")
        .document(student_id)
    )

    update_data = {
        "xp": new_xp,
        "level": new_level,
        "badge": badge
    }

    if mission_completed:

        update_data[
            "todayMission.completed"
        ] = True

    student_ref.update(
        update_data
    )

    # ==========================================
    # 학급 목표 증가
    # ==========================================

    class_id = student_data.get(
        "classId"
    )

    if class_id:

        db.collection("classes") \
            .document(class_id) \
            .update({
                "goalCurrent":
                Increment(1)
            })

    # ==========================================
    # 보상 기록
    # ==========================================

    reward_ref.set({
        "studentId": student_id,
        "sessionId": session_id,
        "xp": xp_gain,
        "missionCompleted":
        mission_completed
    })

    # ==========================================
    # 응답
    # ==========================================

    return {
        "success": True,

        "rewardTransactionId":
        reward_transaction_id,

        "reward": {
            "xp": xp_gain,
            "missionCompleted":
            mission_completed
        },

        "student": {
            "xp": new_xp,
            "level": new_level,
            "badge": badge
        },

        "mission": {
            "missionId": mission_id,
            "type": mission_type,
            "completed":
            mission_completed
        },

        "collection":
        collection_result
    }