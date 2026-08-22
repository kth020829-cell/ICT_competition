from fastapi import APIRouter, Header, HTTPException

from app.firebase import db


router = APIRouter(
    prefix="/collection",
    tags=["Collection"]
)


# ==========================================
# 학생 인증
# ==========================================

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

    student_doc = student_docs[0]

    return student_doc.id, student_doc.to_dict()


# ==========================================
# GET /collection
# 전체 도감 조회
# ==========================================

@router.get("")
def get_collection(
    student_token: str | None = Header(default=None)
):

    # --------------------------------------
    # 1. 학생 인증
    # --------------------------------------

    student_id, student_data = get_student(
        student_token
    )


    # --------------------------------------
    # 2. 모든 카드 조회
    # --------------------------------------

    card_docs = (
        db.collection("card")
        .stream()
    )


    # --------------------------------------
    # 3. 학생의 collection 서브컬렉션 조회
    # --------------------------------------

    student_collection_ref = (
        db.collection("students")
        .document(student_id)
        .collection("collection")
    )

    student_collection_docs = (
        student_collection_ref
        .stream()
    )


    # cardId를 key로 사용하기 위해
    student_collection = {}

    for collection_doc in student_collection_docs:

        collection_data = collection_doc.to_dict()

        student_collection[
            collection_doc.id
        ] = collection_data


    # --------------------------------------
    # 4. 도감 생성
    # --------------------------------------

    collections = []

    collected_count = 0
    total_count = 0

    for card_doc in card_docs:

        card_data = card_doc.to_dict()

        card_id = card_doc.id

        collection_data = student_collection.get(
            card_id,
            {}
        )

        # collection 서브컬렉션에 문서가 존재하면
        # 획득한 카드로 판단
        collected = bool(collection_data)

        count = collection_data.get(
            "count",
            0
        )

        if collected:
            collected_count += 1

        total_count += 1


        collections.append({
            "cardId": card_id,
            "name": card_data.get("name"),
            "type": card_data.get("type"),
            "class": card_data.get("class"),
            "level": card_data.get("level"),
            "needsActions": card_data.get(
                "needsActions"
            ),
            "collected": collected,
            "count": count
        })


    # --------------------------------------
    # 5. 응답
    # --------------------------------------

    return {
        "success": True,
        "studentId": student_id,
        "totalCount": total_count,
        "collectedCount": collected_count,
        "collections": collections
    }


# ==========================================
# GET /collection/{card_id}
# 특정 카드 조회
# ==========================================

@router.get("/{card_id}")
def get_collection_card(
    card_id: str,
    student_token: str | None = Header(default=None)
):

    # --------------------------------------
    # 1. 학생 인증
    # --------------------------------------

    student_id, student_data = get_student(
        student_token
    )


    # --------------------------------------
    # 2. 카드 조회
    # --------------------------------------

    card_ref = (
        db.collection("card")
        .document(card_id)
    )

    card_doc = card_ref.get()

    if not card_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 카드입니다."
        )

    card_data = card_doc.to_dict()


    # --------------------------------------
    # 3. 학생 collection 조회
    # --------------------------------------

    collection_ref = (
        db.collection("students")
        .document(student_id)
        .collection("collection")
        .document(card_id)
    )

    collection_doc = collection_ref.get()


    # --------------------------------------
    # 4. 아직 획득하지 않은 카드
    # --------------------------------------

    if not collection_doc.exists:

        return {
            "success": True,
            "cardId": card_id,
            "name": card_data.get("name"),
            "type": card_data.get("type"),
            "class": card_data.get("class"),
            "level": card_data.get("level"),
            "collected": False,
            "count": 0,
            "message": "아직 발견하지 않은 카드입니다."
        }


    # --------------------------------------
    # 5. 획득한 카드
    # --------------------------------------

    collection_data = collection_doc.to_dict()

    count = collection_data.get(
        "count",
        0
    )


    return {
        "success": True,
        "cardId": card_id,
        "name": card_data.get("name"),
        "type": card_data.get("type"),
        "class": card_data.get("class"),
        "level": card_data.get("level"),
        "needsActions": card_data.get(
            "needsActions"
        ),
        "collected": True,
        "count": count
    }