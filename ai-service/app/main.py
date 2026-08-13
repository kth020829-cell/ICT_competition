"""다시봄 스쿨 AI 추론 서버.

프론트엔드 → 백엔드 메인 → **AI 추론 서버** → JSON → 백엔드 검증·보상 → 프론트엔드
프론트엔드가 이 서버를 직접 호출하지 않는다. (지시서 §5.1)
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analyze, compare, health
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("AI_MODE=%s 로 기동합니다.", settings.ai_mode)
    if settings.ai_mode == "mock":
        logger.info("mock 모드: 고정 JSON을 반환합니다. 모델·API 키가 없어도 동작합니다.")
    if not settings.yolo_weights_path.exists():
        logger.warning("YOLO 가중치 없음: %s (STEP 2에서 필요)", settings.yolo_weights_path)
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY 미설정 (STEP 4에서 필요)")

    if settings.ai_mode == "remote" and settings.warmup_on_startup:
        _warmup()
    yield


def _warmup() -> None:
    """모델을 미리 로드하고 한 번 추론해 둔다.

    하지 않으면 첫 요청이 4~5초 걸린다. 발표 시연에서 첫 사진이 가장 중요한데
    거기서 멈춰 보이면 안 된다.
    """
    blank = None
    try:
        from PIL import Image

        from app.services import detector

        blank = Image.new("RGB", (640, 640), (128, 128, 128))
        detector.detect(blank)
        logger.info("YOLO 워밍업 완료")
    except Exception as exc:  # 워밍업 실패가 기동을 막아서는 안 된다
        logger.warning("YOLO 워밍업 건너뜀: %s", exc)

    # 얼굴 검출도 첫 호출에 tflite 로드가 걸린다. 같이 데워 둔다.
    try:
        from PIL import Image

        from app.services import safety

        safety.detect_faces(blank or Image.new("RGB", (256, 256), (128, 128, 128)))
        logger.info("BlazeFace 워밍업 완료")
    except Exception as exc:
        logger.warning("BlazeFace 워밍업 건너뜀: %s", exc)


app = FastAPI(
    lifespan=lifespan,
    title="다시봄 스쿨 AI 추론 서버",
    version="0.1.0",
    description=(
        "초등 고학년 재활용 교육 웹앱의 AI 파트. "
        "YOLO11n으로 검출·크롭하고 Claude VLM이 종류와 상태를 최종 판정한다.\n\n"
        "**AI 판정은 참고용이며, 배출 기준은 충북·청주시 기준이다.**"
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(compare.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """검증 실패를 백엔드가 읽기 쉬운 형태로 되돌린다.

    추론 실패(얼굴 검출·타임아웃 등)는 200 + status/error 로 오지만,
    요청 자체가 잘못된 경우는 422로 구분해서 알린다.
    """
    logger.warning("validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "detail": "요청 형식이 올바르지 않습니다.",
            "errors": [
                {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
                for e in exc.errors()
            ],
        },
    )


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "dasibom-ai",
        "aiMode": settings.ai_mode,
        "docs": "/docs",
        "health": "/health",
    }
