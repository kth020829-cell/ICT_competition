from fastapi import APIRouter, Header, HTTPException
from google.cloud.firestore_v1 import Increment

from app.firebase import db
from app.services.collection import collect_card
from app.services.mission import check_mission


router = APIRouter(
    prefix="/rewards",
    tags=["Reward"]
)


# ==========================================
# POST /rewards/{session_id}
# ==========================================

@router.post("/{session_id}")
def give_reward(
    session_id: str,
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
    # 2. 세션 확인
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
    # 3. 세션 소유자 확인
    # ==========================================

    if session_data.get(
        "studentId"
    ) != student_id:

        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )


    # ==========================================
    # 4. 세션 완료 확인
    # ==========================================

    if session_data.get(
        "status"
    ) != "COMPLETED":

        raise HTTPException(
            status_code=400,
            detail="완료된 세션만 보상을 받을 수 있습니다."
        )


    # ==========================================
    # 5. 중복 보상 방지
    # ==========================================

    reward_transaction_id = (
        f"{session_id}_reward"
    )

    reward_ref = (
        db.collection("rewardTransactions")
        .document(reward_transaction_id)
    )

    reward_doc = reward_ref.get()

    if reward_doc.exists:

        return {
            "success": True,
            "message": "이미 보상을 지급받은 세션입니다.",
            "rewardTransactionId":
                reward_transaction_id
        }


    # ==========================================
    # 6. AI 결과 가져오기
    # ==========================================

    result_data = session_data.get(
        "result",
        {}
    )

    detected_class = result_data.get(
        "detectedClass"
    )

    if not detected_class:
        raise HTTPException(
            status_code=400,
            detail="세션에 쓰레기 판정 결과가 없습니다."
        )


    # ==========================================
    # 7. 카드 조회
    # ==========================================

    card_query = (
        db.collection("card")
        .where(
            "type",
            "==",
            detected_class
        )
        .limit(1)
        .stream()
    )

    card_docs = list(card_query)

    card_data = None
    card_id = None

    if card_docs:

        card_doc = card_docs[0]

        card_id = card_doc.id

        card_data = card_doc.to_dict()


    # ==========================================
    # 8. 기존 도감 수집 여부 확인
    #
    # NEW_CARD 미션을 판정하기 위해
    # 반드시 collect_card()보다 먼저 확인
    # ==========================================

    student_collection = student_data.get(
        "collection",
        {}
    )

    existing_collection = {}

    if card_id:

        existing_collection = (
            student_collection.get(
                card_id,
                {}
            )
        )

    already_collected = (
        existing_collection.get(
            "collected",
            False
        )
    )


    # ==========================================
    # 9. 오늘의 미션 확인
    # ==========================================

    mission_id = student_data.get(
        "todayMissionId"
    )

    mission_type = student_data.get(
        "todayMissionType"
    )


    # ==========================================
    # 10. 미션 판정
    #
    # 도감 추가보다 먼저 실행
    # ==========================================

    mission_result = {
        "missionId": mission_id,
        "type": mission_type,
        "completed": False
    }

    if mission_type:

        mission_result = check_mission(
            mission_type=mission_type,
            session_data=session_data,
            card_data=card_data,
            already_collected=already_collected
        )


    # ==========================================
    # 11. 도감 자동 수집
    #
    # 미션 판정 이후 실행
    # ==========================================

    collection_result = {
        "registered": False,
        "cardId": None,
        "isNew": False,
        "count": 0
    }

    collection_result = collect_card(
        student_id=student_id,
        detected_class=detected_class
    )


    # ==========================================
    # 12. XP 계산
    #
    # 기본 보상 10 XP
    # 미션 성공 시 +30 XP
    # ==========================================

    BASE_XP = 10
    MISSION_XP = 30

    xp_gain = BASE_XP

    if mission_result["COMPLETED"]:
        xp_gain += MISSION_XP


    # ==========================================
    # 13. 누적 XP 계산
    # ==========================================

    current_xp = student_data.get(
        "xp",
        0
    )

    new_xp = current_xp + xp_gain


    # ==========================================
    # 14. 레벨 계산
    #
    # XP는 초기화하지 않고 누적
    #
    # 0~49   → Level 1
    # 50~99  → Level 2
    # 100~149 → Level 3
    # ==========================================

    new_level = (
        new_xp // 50
    ) + 1


    # ==========================================
    # 15. 뱃지 계산
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
    # 16. 학생 정보 업데이트
    # ==========================================

    student_ref = (
        db.collection("students")
        .document(student_id)
    )

    student_ref.update({

        "xp": new_xp,

        "level": new_level,

        "badge": badge
    })


    # ==========================================
    # 17. 학급 공동 목표 업데이트
    # ==========================================

    class_id = student_data.get(
        "classId"
    )

    if class_id:

        class_ref = (
            db.collection("classes")
            .document(str(class_id))
        )

        class_doc = class_ref.get()

        if class_doc.exists:

            class_ref.update({
                "goalCurrent": Increment(1)
            })


    # ==========================================
    # 18. 보상 거래 기록
    # ==========================================

    reward_ref.set({

        "studentId": student_id,

        "sessionId": session_id,

        "xp": xp_gain,

        "missionId":
            mission_result["missionId"],

        "missionType":
            mission_result["type"],

        "missionCompleted":
            mission_result["completed"],

        "cardId":
            collection_result.get("cardId"),

        "isNewCard":
            collection_result.get("isNew", False),

        "rewardTransactionId":
            reward_transaction_id
    })


    # ==========================================
    # 19. 응답
    # ==========================================

    return {

        "success": True,
        "sessionId": session_id,
        "rewardTransactionId":
            reward_transaction_id,

        "reward": {

            "xp": xp_gain,

            "missionCompleted":
                mission_result["completed"]
        },

        "mission": mission_result,

        "student": {

            "xp": new_xp,

            "level": new_level,

            "badge": badge
        },

        "collection":
            collection_result
    }
