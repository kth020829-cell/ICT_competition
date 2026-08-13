"""AI 추론 서버 → 백엔드 응답 스키마 (지시서 §5.5, §5.6).

계약 원칙
- AI 서버는 **항상 HTTP 200 + 구조화된 본문**을 반환한다. 얼굴 검출·타임아웃 같은
  실패도 `status`/`error` 로 표현한다. 백엔드가 상태코드 분기 없이 한 경로로
  파싱할 수 있게 하려는 의도다. (요청 자체가 잘못된 경우만 4xx)
- 자유 문자열만 주지 않는다. 행동은 반드시 `code` 를 동반한다. (지시서 §5.2)
"""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    ActionCode,
    AnalysisStatus,
    DetectionSource,
    DisposalCategory,
    ErrorCode,
    Phase,
    StateValue,
)


class CamelModel(BaseModel):
    """응답 JSON은 camelCase로 나간다."""

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


class BoundingBox(CamelModel):
    """0~1 정규화 좌표. 원본 해상도에 독립적이라 프론트가 그대로 오버레이할 수 있다."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)


class Safety(CamelModel):
    face_detected: bool = Field(alias="faceDetected")
    is_waste_image: bool = Field(alias="isWasteImage")


class Detection(CamelModel):
    class_code: str | None = Field(default=None, alias="classCode")
    class_name_ko: str | None = Field(default=None, alias="classNameKo")
    #: VLM이 판정한 세부 품목명. classNameKo보다 우선한다. (지시서 §5.5)
    item_name_ko: str | None = Field(default=None, alias="itemNameKo")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: DetectionSource = DetectionSource.YOLO
    bounding_box: BoundingBox | None = Field(default=None, alias="boundingBox")


class StateItem(CamelModel):
    value: StateValue
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RequiredAction(CamelModel):
    code: ActionCode
    label_ko: str = Field(alias="labelKo")
    required: bool = True


class Disposal(CamelModel):
    category_code: DisposalCategory = Field(alias="categoryCode")
    category_name_ko: str = Field(alias="categoryNameKo")
    #: recycling_rules.json 상의 규칙 식별자. 기획서에 근거로 인용한다.
    rule_id: str | None = Field(default=None, alias="ruleId")


class Feedback(CamelModel):
    title: str
    message: str
    #: TTS용. 이모지·기호를 뺀 순수 발화 텍스트라 message와 다를 수 있다.
    tts_text: str = Field(alias="ttsText")


class Comparison(CamelModel):
    """Before/After 비교 결과 (지시서 §5.6). AFTER 단계에서만 채워진다."""

    same_class: bool = Field(alias="sameClass")
    improved_actions: list[ActionCode] = Field(default_factory=list, alias="improvedActions")
    remaining_actions: list[ActionCode] = Field(default_factory=list, alias="remainingActions")
    regressed_actions: list[ActionCode] = Field(default_factory=list, alias="regressedActions")


class Processing(CamelModel):
    used_vlm: bool = Field(default=False, alias="usedVlm")
    cache_hit: bool = Field(default=False, alias="cacheHit")
    elapsed_ms: int = Field(default=0, alias="elapsedMs")
    model_version: str = Field(alias="modelVersion")
    prompt_version: str = Field(alias="promptVersion")
    rule_version: str = Field(alias="ruleVersion")

    # `model_` 접두사가 pydantic 예약어와 겹치는 것을 허용한다.
    model_config = ConfigDict(
        populate_by_name=True, use_enum_values=True, protected_namespaces=()
    )


class AnalysisError(CamelModel):
    """지시서 §5.7 오류 코드. status가 REJECTED/FAILED일 때 채워진다."""

    code: ErrorCode
    message_ko: str = Field(alias="messageKo")
    retryable: bool = True


class AnalyzeResponse(CamelModel):
    analysis_id: str = Field(alias="analysisId")
    scan_session_id: str = Field(alias="scanSessionId")
    phase: Phase
    status: AnalysisStatus

    safety: Safety
    detection: Detection
    #: 품목별 키가 다르다. 해당 없는 항목은 not_applicable. (지시서 §5.3)
    states: dict[str, StateItem] = Field(default_factory=dict)
    required_actions: list[RequiredAction] = Field(
        default_factory=list, alias="requiredActions"
    )
    disposal: Disposal | None = None
    feedback: Feedback

    comparison: Comparison | None = None
    #: 참고값. 실제 보상 지급은 백엔드가 결정한다. (지시서 §5.6)
    reward_eligible: bool | None = Field(default=None, alias="rewardEligible")

    error: AnalysisError | None = None
    processing: Processing


class CompareResponse(CamelModel):
    """저장된 두 분석 결과를 다시 비교할 때의 응답."""

    before_analysis_id: str = Field(alias="beforeAnalysisId")
    after_analysis_id: str = Field(alias="afterAnalysisId")
    status: AnalysisStatus
    comparison: Comparison
    reward_eligible: bool = Field(alias="rewardEligible")
    feedback: Feedback


class HealthResponse(CamelModel):
    status: str
    ai_mode: str = Field(alias="aiMode")
    model_version: str = Field(alias="modelVersion")
    prompt_version: str = Field(alias="promptVersion")
    rule_version: str = Field(alias="ruleVersion")
    #: 실제 추론에 필요한 자산이 준비됐는지. mock 모드에서는 전부 False일 수 있다.
    checks: dict[str, bool] = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True, use_enum_values=True, protected_namespaces=()
    )
