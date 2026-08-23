import os

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# 키 파일 경로는 환경변수로 받는다. 파일 자체는 .gitignore 대상이고
# 저장소에 올리지 않는다 — 2026-08-24에 이 키가 public 저장소에 노출되어
# Google로부터 사용 중지 통보를 받은 적이 있다.
KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "firebase_key.json")

if not os.path.exists(KEY_PATH):
    raise RuntimeError(
        f"Firebase 키 파일을 찾을 수 없다: {KEY_PATH}\n"
        "Firebase 콘솔 → 프로젝트 설정 → 서비스 계정 → '새 비공개 키 생성'으로\n"
        "받은 JSON을 backend/firebase_key.json 에 두거나, FIREBASE_KEY_PATH 를 설정한다.\n"
        "이 파일은 절대 커밋하지 않는다."
    )

cred = credentials.Certificate(KEY_PATH)

firebase_admin.initialize_app(cred)

db = firestore.client()
