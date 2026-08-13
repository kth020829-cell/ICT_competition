"""POST /v1/analyze — 이미지 1장 분석 (지시서 §5.4, §5.5).

AI_MODE에 따라 처리 경로가 갈린다.
- mock   : 고정 JSON. 백엔드 연동용.
- remote : 실제 파이프라인 (STEP 2~8에서 구현).
- cached : 이미지 해시 캐시 (STEP 9에서 구현).
"""

import logging

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from app.core.config import get_settings
from app.mocks import scenarios
from app.schemas.request import AnalyzeRequest, analyze_form
from app.schemas.response import AnalyzeResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["analyze"])

#: 클라이언트가 긴 변 1024px로 리사이즈해 올린다는 전제 (지시서 §10).
#: 그래도 원본을 그대로 올리는 경우를 대비해 넉넉히 잡는다.
MAX_IMAGE_BYTES = 12 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.post("/analyze", response_model=AnalyzeResponse, response_model_by_alias=True)
async def analyze(
    image: UploadFile = File(..., description="분석할 사진 1장"),
    req: AnalyzeRequest = Depends(analyze_form),
    mock_scenario_field: str | None = Form(None, alias="mockScenario"),
    mock_scenario_header: str | None = Header(None, alias="X-Mock-Scenario"),
) -> AnalyzeResponse:
    settings = get_settings()

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="빈 이미지입니다.")
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"이미지가 너무 큽니다. 최대 {MAX_IMAGE_BYTES // (1024 * 1024)}MB.",
        )
    if image.content_type and image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415, detail=f"지원하지 않는 형식입니다: {image.content_type}"
        )

    if settings.ai_mode in {"remote", "cached"}:
        from app.services import pipeline  # 무거운 의존성이라 필요할 때만 임포트한다
        from app.services.detector import WeightsNotFoundError
        from app.services.rag import RulesNotFoundError
        from app.services.safety import FaceModelNotFoundError

        try:
            return pipeline.run(payload, req)
        except (WeightsNotFoundError, FaceModelNotFoundError, RulesNotFoundError) as exc:
            # 자산이 없으면 '서비스 미준비'다. 추론 실패(200 + error)와 구분한다.
            # 특히 얼굴 검출 모델이 없을 때 조용히 통과시키면 아동 얼굴이 그대로
            # VLM으로 넘어간다. 실패를 드러내는 편이 안전하다. (지시서 §11-5)
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    scenario_name = mock_scenario_field or mock_scenario_header
    if scenario_name and scenario_name not in scenarios.SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"알 수 없는 mock 시나리오 '{scenario_name}'. "
            f"사용 가능: {sorted(scenarios.SCENARIOS)}",
        )

    handler = scenarios.resolve(scenario_name, req.phase)
    response = handler(req)

    logger.info(
        "analyze mock scenario=%s phase=%s session=%s bytes=%d -> %s",
        handler.__name__,
        req.phase,
        req.scan_session_id,
        len(payload),
        response.status,
    )
    return response


@router.get("/mock/scenarios", tags=["mock"])
async def list_scenarios() -> dict[str, object]:
    """백엔드 담당자가 어떤 시나리오를 부를 수 있는지 확인하는 용도."""
    return {
        "scenarios": sorted(scenarios.SCENARIOS),
        "defaultByPhase": dict(scenarios.DEFAULT_BY_PHASE),
        "howTo": "폼 필드 mockScenario 또는 헤더 X-Mock-Scenario 로 지정",
    }
