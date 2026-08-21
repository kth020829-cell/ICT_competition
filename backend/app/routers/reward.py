from fastapi import APIRouter, Header, HTTPException
from app.firebase import db
from app.services.collection import collect_card

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

    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )


    # ==========================================
    # 4. 세션 완료 확인
    # ==========================================

    if session_data.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료된 세션만 보상을 받을 수 있습니다."
        )


    # ==========================================
    # 5. 중복 보상 방지
    # ==========================================

    reward_transaction_id = f"{session_id}_reward"

    reward_ref = (
        db.collection("rewardTransactions")
        .document(reward_transaction_id)
    )

    reward_doc = reward_ref.get()

    if reward_doc.exists:
        return {
            "success": True,
            "message": "이미 보상을 지급받은 세션입니다.",
            "rewardTransactionId": reward_transaction_id
        }


    # ==========================================
    # 6. 기본 XP
    # ==========================================

    xp_gain = 10


    # ==========================================
    # 7. 미션 보너스
    # ==========================================

    mission_completed = False

    # TODO:
    # 나중에 미션 판정 로직 연결
    #
    # mission_completed = check_mission(...)

    if mission_completed:
        xp_gain += 30


    # ==========================================
    # 8. 현재 XP
    # ==========================================

    current_xp = student_data.get("xp", 0)

    new_xp = current_xp + xp_gain


    # ==========================================
    # 9. 레벨 계산
    # ==========================================

    new_level = (new_xp // 50) + 1


    # ==========================================
    # 10. 뱃지 계산
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
    # 11. 도감 자동 수집
    # ==========================================

    collection_result = {
        "registered": False,
        "cardId": None,
        "isNew": False,
        "count": 0
    }

    result_data = session_data.get("result")

    if result_data:

        detected_class = result_data.get(
            "detectedClass"
        )

        if detected_class:

            collection_result = collect_card(
                student_id=student_id,
                detected_class=detected_class
            )


    # ==========================================
    # 12. 학생 정보 업데이트
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
    # 13. 보상 거래 기록
    # ==========================================

    reward_ref.set({
        "studentId": student_id,
        "sessionId": session_id,
        "xp": xp_gain,
        "missionCompleted": mission_completed,
        "rewardTransactionId": reward_transaction_id
    })


    # ==========================================
    # 14. 응답
    # ==========================================

    return {
        "success": True,
        "sessionId": session_id,
        "rewardTransactionId": reward_transaction_id,

        "reward": {
            "xp": xp_gain,
            "missionCompleted": mission_completed
        },

        "student": {
            "xp": new_xp,
            "level": new_level,
            "badge": badge
        },

        "collection": collection_result
    }