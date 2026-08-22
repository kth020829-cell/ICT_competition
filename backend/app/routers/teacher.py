from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.firebase import db

import random


router = APIRouter(
    prefix="/teacher",
    tags=["Teacher"]
)

class ClassCreateRequest(BaseModel):
    school: str
    grade: int
    className: int
    goalTarget: int

# ==========================================
# Request Model
# ==========================================

class TeacherCreateRequest(BaseModel):
    name: str
    email: str

class ClassLockRequest(BaseModel):
    locked: bool

def generate_class_code():

    while True:

        code = int(
            random.randint(100000, 999999)
        )

        classes = (
            db.collection("classes")
            .where(
                "classCode",
                "==",
                code
            )
            .limit(1)
            .stream()
        )

        if not list(classes):
            return code


# ==========================================
# POST /teacher
# 선생님 생성
# ==========================================

@router.post("")
def create_teacher(
    request: TeacherCreateRequest
):

    # 이메일 중복 확인
    teachers = (
        db.collection("teachers")
        .where(
            "email",
            "==",
            request.email
        )
        .limit(1)
        .stream()
    )

    if list(teachers):
        raise HTTPException(
            status_code=409,
            detail="이미 등록된 이메일입니다."
        )

    # Firestore 자동 ID
    teacher_ref = db.collection("teachers").document()

    teacher_ref.set({
        "name": request.name,
        "email": request.email
    })

    return {
        "success": True,
        "teacherId": teacher_ref.id,
        "name": request.name,
        "email": request.email
    }

@router.post("/classes")
def create_class(
    request: ClassCreateRequest,
    teacher_id: str = Header(...)
):

    # ==========================================
    # 1. 선생님 확인
    # ==========================================

    teacher_ref = (
        db.collection("teachers")
        .document(teacher_id)
    )

    teacher_doc = teacher_ref.get()

    if not teacher_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 선생님입니다."
        )


    # ==========================================
    # 2. 학급 코드 생성
    # ==========================================

    class_code = generate_class_code()


    # ==========================================
    # 3. 학급 생성
    # ==========================================

    class_ref = (
        db.collection("classes")
        .document()
    )

    class_ref.set({
        "teacherId": teacher_id,
        "classCode": class_code,
        "className": request.className,
        "goalCurrent": 0,
        "goalTarget": request.goalTarget,
        "grade": request.grade,
        "locked": False,
        "school": request.school,
        "studentCount": 0
    })


    return {
        "success": True,
        "classId": class_ref.id,
        "classCode": class_code,
        "className": request.className,
        "grade": request.grade,
        "school": request.school
    }

@router.get("/classes/{class_id}")
def get_class(
    class_id: str,
    teacher_id: str = Header(...)
):

    class_ref = (
        db.collection("classes")
        .document(class_id)
    )

    class_doc = class_ref.get()

    if not class_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 학급입니다."
        )

    class_data = class_doc.to_dict()

    # 학급 소유자 확인
    if class_data.get("teacherId") != teacher_id:
        raise HTTPException(
            status_code=403,
            detail="이 학급을 조회할 권한이 없습니다."
        )

    return {
        "success": True,
        "classId": class_id,
        "classCode": class_data.get("classCode"),
        "className": class_data.get("className"),
        "grade": class_data.get("grade"),
        "school": class_data.get("school"),
        "goalCurrent": class_data.get("goalCurrent", 0),
        "goalTarget": class_data.get("goalTarget", 0),
        "locked": class_data.get("locked", False),
        "studentCount": class_data.get("studentCount", 0)
    }

@router.patch("/classes/{class_id}/lock")
def update_class_lock(
    class_id: str,
    request: ClassLockRequest,
    teacher_id: str = Header(...)
):

    class_ref = (
        db.collection("classes")
        .document(class_id)
    )

    class_doc = class_ref.get()

    if not class_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 학급입니다."
        )

    class_data = class_doc.to_dict()

    if class_data.get("teacherId") != teacher_id:
        raise HTTPException(
            status_code=403,
            detail="이 학급을 관리할 권한이 없습니다."
        )

    class_ref.update({
        "locked": request.locked
    })

    return {
        "success": True,
        "classId": class_id,
        "locked": request.locked
    }

@router.get("/classes/{class_id}/code")
def get_class_code(
    class_id: str,
    teacher_id: str = Header(...)
):

    class_ref = (
        db.collection("classes")
        .document(class_id)
    )

    class_doc = class_ref.get()

    if not class_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 학급입니다."
        )

    class_data = class_doc.to_dict()

    if class_data.get("teacherId") != teacher_id:
        raise HTTPException(
            status_code=403,
            detail="권한이 없습니다."
        )

    return {
        "success": True,
        "classCode": class_data.get("classCode"),
        "locked": class_data.get("locked", False)
    }