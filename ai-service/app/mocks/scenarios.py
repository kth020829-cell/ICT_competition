"""STEP 1 — Mock 시나리오 (지시서 §9 STEP 1).

백엔드 담당자가 모델 없이 즉시 연동을 시작할 수 있도록 고정 JSON을 반환한다.
시나리오는 요청의 `X-Mock-Scenario` 헤더 또는 `mockScenario` 폼 필드로 고른다.
지정이 없으면 phase에 따라 기본 시나리오가 선택된다.

여기의 응답은 **실제 추론이 STEP 2~8에서 채워질 자리의 모양**이다.
따라서 값은 가짜지만 스키마·코드값은 진짜와 완전히 같아야 한다.
"""

from collections.abc import Callable

from app.core.config import get_settings
from app.core.ids import new_analysis_id
from app.schemas.enums import (
    ACTION_LABEL_KO,
    CLASS_NAME_KO,
    DISPOSAL_NAME_KO,
    ERROR_RETRYABLE,
    STATE_SCHEMA,
    ActionCode,
    AnalysisStatus,
    DetectionSource,
    DisposalCategory,
    ErrorCode,
    Phase,
    StateValue,
    YoloClass,
)
from app.schemas.request import AnalyzeRequest
from app.schemas.response import (
    AnalysisError,
    AnalyzeResponse,
    BoundingBox,
    Comparison,
    Detection,
    Disposal,
    Feedback,
    Processing,
    RequiredAction,
    Safety,
    StateItem,
)


# --------------------------------------------------------------------------
# 조립 헬퍼
# --------------------------------------------------------------------------
def _states(class_code: str, known: dict[str, tuple[str, float]]) -> dict[str, StateItem]:
    """품목 스키마의 모든 키를 채운다.

    지시서 §5.3대로 해당 없는 키는 `not_applicable`로 명시한다. 키를 아예
    빼버리면 백엔드가 '판정 실패'와 '해당 없음'을 구분할 수 없다.
    """
    result: dict[str, StateItem] = {}
    for key in STATE_SCHEMA.get(class_code, []):
        if key in known:
            value, confidence = known[key]
            result[key] = StateItem(value=StateValue(value), confidence=confidence)
        else:
            result[key] = StateItem(value=StateValue.NOT_APPLICABLE, confidence=1.0)
    return result


def _actions(*codes: ActionCode) -> list[RequiredAction]:
    return [
        RequiredAction(code=code, labelKo=ACTION_LABEL_KO[code], required=True)
        for code in codes
    ]


def _disposal(category: DisposalCategory, rule_id: str) -> Disposal:
    return Disposal(
        categoryCode=category,
        categoryNameKo=DISPOSAL_NAME_KO[category],
        ruleId=rule_id,
    )


def _processing(*, used_vlm: bool = True, cache_hit: bool = False, elapsed_ms: int = 0) -> Processing:
    settings = get_settings()
    return Processing(
        usedVlm=used_vlm,
        cacheHit=cache_hit,
        elapsedMs=elapsed_ms,
        modelVersion=settings.model_version,
        promptVersion=settings.prompt_version,
        ruleVersion=settings.rule_version,
    )


def _rejected(
    req: AnalyzeRequest,
    code: ErrorCode,
    *,
    title: str,
    message: str,
    face_detected: bool = False,
    is_waste_image: bool = True,
    status: AnalysisStatus = AnalysisStatus.REJECTED,
    elapsed_ms: int = 0,
    used_vlm: bool = False,
) -> AnalyzeResponse:
    """거부/실패 응답. 아이에게는 오류가 아니라 '다시 찍어보자'로 전달된다."""
    return AnalyzeResponse(
        analysisId=new_analysis_id(),
        scanSessionId=req.scan_session_id,
        phase=req.phase,
        status=status,
        safety=Safety(faceDetected=face_detected, isWasteImage=is_waste_image),
        detection=Detection(source=DetectionSource.VLM_ONLY, confidence=0.0),
        states={},
        requiredActions=[],
        disposal=None,
        feedback=Feedback(title=title, message=message, ttsText=message),
        error=AnalysisError(
            code=code,
            messageKo=message,
            retryable=ERROR_RETRYABLE[code],
        ),
        processing=_processing(used_vlm=used_vlm, elapsed_ms=elapsed_ms),
    )


# --------------------------------------------------------------------------
# 정상 경로
# --------------------------------------------------------------------------
def pet_action_required(req: AnalyzeRequest) -> AnalyzeResponse:
    """Before 단계의 표준 응답.

    지시서 §4.3 — Before의 정답은 배출 결론이 아니라 '준비 필요 안내'다.
    그래서 status는 ACTION_REQUIRED이고 disposal은 아직 확정하지 않는다.
    """
    return AnalyzeResponse(
        analysisId=new_analysis_id(),
        scanSessionId=req.scan_session_id,
        phase=req.phase,
        status=AnalysisStatus.ACTION_REQUIRED,
        safety=Safety(faceDetected=False, isWasteImage=True),
        detection=Detection(
            classCode=YoloClass.PET,
            classNameKo=CLASS_NAME_KO[YoloClass.PET],
            itemNameKo="투명 페트병",
            confidence=0.93,
            source=DetectionSource.YOLO,
            boundingBox=BoundingBox(x=0.18, y=0.12, width=0.61, height=0.74),
        ),
        states=_states(
            YoloClass.PET,
            {
                "labelAttached": ("yes", 0.89),
                "capAttached": ("yes", 0.94),
                "contentRemaining": ("no", 0.72),
                "flattened": ("no", 0.83),
            },
        ),
        requiredActions=_actions(ActionCode.REMOVE_LABEL, ActionCode.CRUSH),
        disposal=_disposal(DisposalCategory.CLEAR_PET_BIN, "CHEONGJU-PET-001"),
        feedback=Feedback(
            title="페트병을 찾았어!",
            message="라벨을 떼고 납작하게 눌러보자.",
            ttsText="페트병을 찾았어. 라벨을 떼고 납작하게 눌러보자.",
        ),
        processing=_processing(elapsed_ms=2840),
    )


def pet_completed(req: AnalyzeRequest) -> AnalyzeResponse:
    """준비가 끝난 상태. 배출 결론을 제시해도 되는 유일한 시점이다.

    투명 페트병은 압착 후 **뚜껑을 닫아서** 배출한다 (지시서 §4.4).
    그래서 capAttached=yes 인데도 REMOVE_CAP을 요구하지 않는다.
    """
    return AnalyzeResponse(
        analysisId=new_analysis_id(),
        scanSessionId=req.scan_session_id,
        phase=req.phase,
        status=AnalysisStatus.COMPLETED,
        safety=Safety(faceDetected=False, isWasteImage=True),
        detection=Detection(
            classCode=YoloClass.PET,
            classNameKo=CLASS_NAME_KO[YoloClass.PET],
            itemNameKo="투명 페트병",
            confidence=0.95,
            source=DetectionSource.YOLO,
            boundingBox=BoundingBox(x=0.22, y=0.30, width=0.55, height=0.42),
        ),
        states=_states(
            YoloClass.PET,
            {
                "labelAttached": ("no", 0.91),
                "capAttached": ("yes", 0.88),
                "contentRemaining": ("no", 0.86),
                "flattened": ("yes", 0.90),
            },
        ),
        requiredActions=[],
        disposal=_disposal(DisposalCategory.CLEAR_PET_BIN, "CHEONGJU-PET-001"),
        feedback=Feedback(
            title="완벽해!",
            message="투명 페트병 전용함에 넣어줘. 뚜껑은 닫은 채로 버리면 돼.",
            ttsText="완벽해! 투명 페트병 전용함에 넣어줘. 뚜껑은 닫은 채로 버리면 돼.",
        ),
        rewardEligible=True,
        processing=_processing(elapsed_ms=2610),
    )


def after_success(req: AnalyzeRequest) -> AnalyzeResponse:
    """After — 요구한 행동을 모두 해냈다."""
    response = pet_completed(req)
    response.phase = Phase.AFTER
    response.status = AnalysisStatus.IMPROVED
    response.comparison = Comparison(
        sameClass=True,
        expectedClass=YoloClass.PET,
        detectedClass=YoloClass.PET,
        improvedActions=[ActionCode.REMOVE_LABEL, ActionCode.CRUSH],
        remainingActions=[],
        regressedActions=[],
    )
    response.reward_eligible = True
    response.feedback = Feedback(
        title="다 해냈어!",
        message="라벨도 떼고 납작하게도 눌렀네. 투명 페트병 전용함에 넣어줘.",
        ttsText="다 해냈어! 라벨도 떼고 납작하게도 눌렀네. 투명 페트병 전용함에 넣어줘.",
    )
    return response


def after_partial(req: AnalyzeRequest) -> AnalyzeResponse:
    """After — 일부만 개선. 남은 행동만 다시 안내하고 해낸 것은 인정한다.

    지시서 §4.2 — After를 절대 기준으로 심판하지 않고 Before와 비교한다.
    """
    return AnalyzeResponse(
        analysisId=new_analysis_id(),
        scanSessionId=req.scan_session_id,
        phase=Phase.AFTER,
        status=AnalysisStatus.PARTIALLY_IMPROVED,
        safety=Safety(faceDetected=False, isWasteImage=True),
        detection=Detection(
            classCode=YoloClass.PET,
            classNameKo=CLASS_NAME_KO[YoloClass.PET],
            itemNameKo="투명 페트병",
            confidence=0.91,
            source=DetectionSource.YOLO,
            boundingBox=BoundingBox(x=0.20, y=0.15, width=0.58, height=0.70),
        ),
        states=_states(
            YoloClass.PET,
            {
                "labelAttached": ("no", 0.87),
                "capAttached": ("yes", 0.92),
                "contentRemaining": ("no", 0.80),
                "flattened": ("no", 0.85),
            },
        ),
        requiredActions=_actions(ActionCode.CRUSH),
        disposal=_disposal(DisposalCategory.CLEAR_PET_BIN, "CHEONGJU-PET-001"),
        feedback=Feedback(
            title="라벨을 뗐구나!",
            message="이제 납작하게 눌러서 한 번만 더 찍어줄래?",
            ttsText="라벨을 뗐구나! 이제 납작하게 눌러서 한 번만 더 찍어줄래?",
        ),
        comparison=Comparison(
            sameClass=True,
            expectedClass=YoloClass.PET,
            detectedClass=YoloClass.PET,
            improvedActions=[ActionCode.REMOVE_LABEL],
            remainingActions=[ActionCode.CRUSH],
            regressedActions=[],
        ),
        rewardEligible=False,
        processing=_processing(elapsed_ms=3120),
    )


# --------------------------------------------------------------------------
# 거부·실패 경로 (지시서 §5.7)
# --------------------------------------------------------------------------
def face_detected(req: AnalyzeRequest) -> AnalyzeResponse:
    return _rejected(
        req,
        ErrorCode.FACE_DETECTED,
        title="얼굴이 같이 찍혔어",
        message="쓰레기만 나오게 다시 찍어줄래?",
        face_detected=True,
        elapsed_ms=180,
    )


def not_waste(req: AnalyzeRequest) -> AnalyzeResponse:
    return _rejected(
        req,
        ErrorCode.NOT_WASTE,
        title="무엇인지 모르겠어",
        message="분리배출할 물건을 가까이서 찍어줄래?",
        is_waste_image=False,
        elapsed_ms=1450,
        used_vlm=True,
    )


def multiple_objects(req: AnalyzeRequest) -> AnalyzeResponse:
    return _rejected(
        req,
        ErrorCode.MULTIPLE_OBJECTS,
        title="물건이 여러 개야",
        message="하나만 골라서 찍어줄래?",
        elapsed_ms=920,
    )


def low_confidence(req: AnalyzeRequest) -> AnalyzeResponse:
    """VLM 폴백까지 시도했는데도 판정하지 못한 경우. (지시서 §5.7)"""
    return _rejected(
        req,
        ErrorCode.LOW_CONFIDENCE,
        title="잘 안 보여",
        message="조금 더 밝은 곳에서 가까이 찍어줄래?",
        elapsed_ms=3380,
        used_vlm=True,
    )


def ai_timeout(req: AnalyzeRequest) -> AnalyzeResponse:
    """status가 REJECTED가 아니라 FAILED다. 아이 잘못이 아니라 서버 문제라서."""
    return _rejected(
        req,
        ErrorCode.AI_TIMEOUT,
        title="잠깐 생각이 길어졌어",
        message="다시 한 번만 찍어줄래?",
        status=AnalysisStatus.FAILED,
        elapsed_ms=20000,
        used_vlm=True,
    )


# --------------------------------------------------------------------------
# 레지스트리
# --------------------------------------------------------------------------
ScenarioFn = Callable[[AnalyzeRequest], AnalyzeResponse]

SCENARIOS: dict[str, ScenarioFn] = {
    "pet_action_required": pet_action_required,
    "pet_completed": pet_completed,
    "after_success": after_success,
    "after_partial": after_partial,
    "face_detected": face_detected,
    "not_waste": not_waste,
    "multiple_objects": multiple_objects,
    "low_confidence": low_confidence,
    "ai_timeout": ai_timeout,
}

#: 시나리오 지정이 없을 때 phase로 고르는 기본값.
DEFAULT_BY_PHASE: dict[str, str] = {
    Phase.BEFORE: "pet_action_required",
    Phase.AFTER: "after_partial",
    Phase.SINGLE: "pet_completed",
}


def resolve(name: str | None, phase: Phase) -> ScenarioFn:
    """시나리오 이름을 해석한다. 알 수 없는 이름이면 phase 기본값으로 떨어진다."""
    if name and name in SCENARIOS:
        return SCENARIOS[name]
    settings = get_settings()
    fallback = DEFAULT_BY_PHASE.get(phase, settings.mock_default_scenario)
    return SCENARIOS[fallback]
