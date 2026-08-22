from datetime import datetime, timezone

from app.firebase import db


def collect_card(
    student_id: str,
    detected_class: str
):
    # ==========================================
    # 1. AI가 판정한 쓰레기 종류로 카드 찾기
    # ==========================================

    cards = (
        db.collection("cards")
        .where(
            "class",
            "==",
            detected_class
        )
        .limit(1)
        .stream()
    )

    card_docs = list(cards)

    # 카드가 존재하지 않는 경우
    if not card_docs:
        return {
            "registered": False,
            "cardId": None,
            "isNew": False,
            "count": 0
        }

    card_doc = card_docs[0]

    card_id = card_doc.id


    # ==========================================
    # 2. 학생의 도감에서 카드 확인
    # ==========================================

    collection_ref = (
        db.collection("students")
        .document(student_id)
        .collection("collection")
        .document(card_id)
    )

    collection_doc = collection_ref.get()


    # ==========================================
    # 3. 처음 발견한 카드
    # ==========================================

    if not collection_doc.exists:

        collection_ref.set({
            "cardId": card_id,
            "count": 1,
            "collectedAt": datetime.now(timezone.utc)
        })

        return {
            "registered": True,
            "cardId": card_id,
            "isNew": True,
            "count": 1
        }


    # ==========================================
    # 4. 이미 발견한 카드
    # ==========================================

    collection_data = collection_doc.to_dict()

    current_count = collection_data.get(
        "count",
        0
    )

    new_count = current_count + 1

    collection_ref.update({
        "count": new_count
    })

    return {
        "registered": True,
        "cardId": card_id,
        "isNew": False,
        "count": new_count
    }