"""GET /health — 기동 확인 및 자산 준비 상태 점검.

`checks` 를 보면 다음 STEP으로 넘어갈 준비가 됐는지 한눈에 알 수 있다.
mock 모드에서는 전부 False여도 정상이다.
"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.response import HealthResponse

router = APIRouter(tags=["health"])


def _cache_entries() -> int:
    """캐시 항목 수. 세다 실패해도 헬스체크가 죽으면 안 된다."""
    try:
        from app.services import cache  # noqa: PLC0415

        return cache.stats()["entries"]
    except Exception:  # 디렉터리 권한 문제 등
        return 0


@router.get("/health", response_model=HealthResponse, response_model_by_alias=True)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        aiMode=settings.ai_mode,
        modelVersion=settings.model_version,
        promptVersion=settings.prompt_version,
        ruleVersion=settings.rule_version,
        checks={
            # STEP 2에 필요
            "yoloWeights": settings.yolo_weights_path.exists(),
            # STEP 3에 필요
            "faceModel": settings.face_model_path.exists(),
            # STEP 4에 필요
            "anthropicApiKey": bool(settings.anthropic_api_key),
            "statePrompt": (settings.prompts_dir / "state_analysis.txt").exists(),
            # STEP 5에 필요
            "recyclingRules": settings.rules_path.exists(),
            "promptsDir": settings.prompts_dir.exists(),
            # STEP 9 — cached 모드로 시연하려면 캐시가 비어 있으면 안 된다.
            "cacheWarm": _cache_entries() > 0,
        },
    )
