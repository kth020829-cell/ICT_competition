from datetime import datetime, timezone

from app.firebase import db


def collect_card(
    student_id: str,
    detected_class: str
):

    # ==========================================
    # 1. 카드 검색
    # ==========================================

    cards = (
        db.collection("card")
        .where(
            "type",
            "==",
            detected_class
        )
        .limit(1)
        .stream()
    )

    card_docs = list(cards)

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
    # 2. 학생 도감 확인
    # ==========================================

    collection_ref = (
        db.collection("students")
        .document(student_id)
        .collection("collection")
        .document(card_id)
    )

    collection_doc = collection_ref.get()


    # ==========================================
    # 3. 최초 수집
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
    # 4. 이미 수집한 카드
    # ==========================================

    collection_data = collection_doc.to_dict()

    count = collection_data.get(
        "count",
        0
    ) + 1

    collection_ref.update({
        "count": count
    })

    return {
        "registered": True,
        "cardId": card_id,
        "isNew": False,
        "count": count
    }