"""POST /v1/compare — 저장된 Before/After 분석을 다시 비교 (지시서 §5.6).

일반 경로에서는 `/v1/analyze` 에 `phase=AFTER` + `beforeAnalysisId` 를 실어 보내면
응답에 `comparison` 이 함께 온다. 이 엔드포인트는 **이미지 재업로드 없이**
백엔드가 보상 판정을 다시 계산하고 싶을 때 쓰는 보조 경로다.

VLM을 부르지 않는다. 이미 판정된 결과 두 개를 견주기만 하므로 비용도 지연도 없다.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.mocks import scenarios  # noqa: F401  (mock 경로 유지용)
from app.schemas.enums import ActionCode, AnalysisStatus
from app.schemas.request import CompareRequest
from app.schemas.response import CompareResponse, Comparison, Feedback
from app.services import analysis_store, before_after, feedback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["compare"])


def _mock_response(req: CompareRequest) -> CompareResponse:
    return CompareResponse(
        beforeAnalysisId=req.before_analysis_id,
        afterAnalysisId=req.after_analysis_id,
        status=AnalysisStatus.PARTIALLY_IMPROVED,
        comparison=Comparison(
            sameClass=True,
            improvedActions=[ActionCode.REMOVE_LABEL],
            remainingActions=[ActionCode.CRUSH],
            regressedActions=[],
        ),
        # 참고값이다. 실제 지급은 백엔드가 결정한다. (지시서 §5.6)
        rewardEligible=False,
        feedback=Feedback(
            title="라벨을 뗐구나!",
            message="이제 납작하게 눌러서 한 번만 더 찍어줄래?",
            ttsText="라벨을 뗐구나! 이제 납작하게 눌러서 한 번만 더 찍어줄래?",
        ),
    )


@router.post("/compare", response_model=CompareResponse, response_model_by_alias=True)
async def compare(req: CompareRequest) -> CompareResponse:
    settings = get_settings()

    if settings.ai_mode == "mock":
        logger.info(
            "compare mock before=%s after=%s", req.before_analysis_id, req.after_analysis_id
        )
        return _mock_response(req)

    before = analysis_store.get(req.before_analysis_id)
    after = analysis_store.get(req.after_analysis_id)

    missing = [
        name
        for name, snap in (("beforeAnalysisId", before), ("afterAnalysisId", after))
        if snap is None
    ]
    if missing:
        # 보관 기간이 지났거나 서버가 재시작됐다. 요청 자체가 잘못된 것이므로 4xx다.
        raise HTTPException(
            status_code=404,
            detail=f"보관된 분석을 찾을 수 없습니다: {', '.join(missing)}. "
            "이미지를 다시 올려 /v1/analyze 로 분석해주세요.",
        )

    comparison = before_after.compare(
        before,
        after_item_name_ko=after.item_name_ko,
        after_class_code=after.class_code,
        after_required_actions=after.required_actions,
    )
    status = before_after.status_for(comparison)

    return CompareResponse(
        beforeAnalysisId=req.before_analysis_id,
        afterAnalysisId=req.after_analysis_id,
        status=status,
        comparison=comparison,
        rewardEligible=before_after.reward_eligible(comparison),
        feedback=feedback.build(status, item_name_ko=after.item_name_ko),
    )
