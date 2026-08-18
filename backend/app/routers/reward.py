from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app.firebase import db


router = APIRouter(
    prefix="/rewards",
    tags=["Reward"]
)


# ==========================================
# POST /rewards/{session_id}
# 보상 지급
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

    if session_data.get("studentId") != student_id:
        raise HTTPException(
            status_code=403,
            detail="이 세션에 접근할 권한이 없습니다."
        )


    # ==========================================
    # 4. 세션 완료 여부 확인
    # ==========================================

    if session_data.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료되지 않은 세션에는 보상을 지급할 수 없습니다."
        )


    # ==========================================
    # 5. 이미 보상받은 세션인지 확인
    # ==========================================

    reward_docs = (
        db.collection("rewardTransactions")
        .where(
            "sessionId",
            "==",
            session_id
        )
        .limit(1)
        .stream()
    )

    existing_rewards = list(reward_docs)

    if existing_rewards:

        existing_reward = existing_rewards[0].to_dict()

        return {
            "success": True,
            "alreadyRewarded": True,
            "sessionId": session_id,
            "rewardTransactionId": existing_rewards[0].id,
            "xpEarned": existing_reward.get("xpEarned", 0),
            "totalXp": student_data.get("xp", 0),
            "message": "이미 보상이 지급된 세션입니다."
        }


    # ==========================================
    # 6. 보상 계산
    # ==========================================

    base_xp = 10
    new_card_xp = 0
    after_xp = 0
    mission_bonus_xp = 0


    # ------------------------------------------
    # 신규 품목 여부
    # ------------------------------------------

    is_new_item = session_data.get(
        "isNewItem",
        False
    )

    if is_new_item:
        new_card_xp = 30


    # ------------------------------------------
    # Before → After 성공
    # ------------------------------------------

    after_data = session_data.get("after")

    if after_data:
        if after_data.get("improved") is True:
            after_xp = 20


    # ------------------------------------------
    # 미션 보너스
    # ------------------------------------------

    mission_completed = session_data.get(
        "missionCompleted",
        False
    )

    if mission_completed:
        mission_bonus_xp = session_data.get(
            "missionBonusXp",
            0
        )


    # ==========================================
    # 7. 총 XP 계산
    # ==========================================

    total_reward_xp = (
        base_xp
        + new_card_xp
        + after_xp
        + mission_bonus_xp
    )


    # ==========================================
    # 8. 학생 기존 XP 확인
    # ==========================================

    current_xp = student_data.get(
        "xp",
        0
    )

    new_xp = current_xp + total_reward_xp


    # ==========================================
    # 9. 레벨 계산
    # ==========================================

    # 임시 레벨 계산
    # 나중에 실제 레벨 테이블로 변경

    new_level = (new_xp // 100) + 1


    # ==========================================
    # 10. 학생 정보 업데이트
    # ==========================================

    db.collection("students").document(student_id).update({
        "xp": new_xp,
        "level": new_level
    })


    # ==========================================
    # 11. 보상 거래 ID 생성
    # ==========================================

    reward_transaction_id = (
        db.collection("rewardTransactions")
        .document()
        .id
    )


    # ==========================================
    # 12. 보상 기록 저장
    # ==========================================

    reward_data = {
        "studentId": student_id,
        "sessionId": session_id,
        "rewardTransactionId": reward_transaction_id,

        "baseXp": base_xp,
        "newCardXp": new_card_xp,
        "afterXp": after_xp,
        "missionBonusXp": mission_bonus_xp,

        "xpEarned": total_reward_xp,

        "createdAt": datetime.now(timezone.utc)
    }


    db.collection("rewardTransactions").document(
        reward_transaction_id
    ).set(reward_data)


    # ==========================================
    # 13. 응답
    # ==========================================

    return {
        "success": True,
        "alreadyRewarded": False,

        "sessionId": session_id,
        "rewardTransactionId": reward_transaction_id,

        "reward": {
            "baseXp": base_xp,
            "newCardXp": new_card_xp,
            "afterXp": after_xp,
            "missionBonusXp": mission_bonus_xp,
            "totalXp": total_reward_xp
        },

        "student": {
            "xp": new_xp,
            "level": new_level
        },

        "message": "보상이 지급되었습니다."
    }