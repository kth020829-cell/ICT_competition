from fastapi import FastAPI
from app.firebase import db

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Hello"}


@app.get("/test/firebase")
def test_firebase():

    db.collection("students").document("test_student").set({
        "badgeCount": 0,
        "collectionCount": 0,
        "joinedAt": "2023-01-01",
        "level": 0,
        "nickname": "테스트학생",
        "xp": 0
    })

    return {
        "success": True,
        "message": "Firestore에 저장했습니다."
    }


@app.get("/test/firebase/read")
def read_firebase():

    doc = (
        db.collection("students")
        .document("test_student")
        .get()
    )

    if not doc.exists:
        return {
            "success": False,
            "message": "학생이 없습니다."
        }

    return {
        "success": True,
        "studentId": doc.id,
        "data": doc.to_dict()
    }