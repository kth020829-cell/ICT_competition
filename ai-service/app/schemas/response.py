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
    #: 명세서 §4가 요구하는 필드. 아직 전용 검출기가 없어 항상 False로 나간다.
    #: 필드를 미리 내보내는 이유는 백엔드·프론트가 분기를 먼저 짜둘 수 있게
    #: 하려는 것이다. 검출기가 붙으면 값만 채워진다.
    dangerous_object_detected: bool = Field(default=False, alias="dangerousObjectDetected")


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
    #: 명세서 §5가 요구하는 두 필드. sameClass가 False일 때 백엔드가
    #: CLASS_MISMATCH 안내를 만들려면 어떤 품목이 어떤 품목으로 바뀐 것인지
    #: 알아야 한다. sameClass 하나만으로는 그 문장을 못 만든다.
    expected_class: str | None = Field(default=None, alias="expectedClass")
    detected_class: str | None = Field(default=None, alias="detectedClass")
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


class SessionResult(CamelModel):
    """백엔드 세션 result 양식 (명세서 §3).

    백엔드 `SessionResultRequest` 와 앞의 6개 필드가 1:1로 맞는다. 백엔드는
    `SessionResultRequest(**응답)` 으로 그대로 받으면 되고, 뒤의 부가 필드는
    pydantic이 알아서 무시한다(v2 기본값 extra="ignore").

    **왜 평평하게 내는가.** 백엔드가 이미 이 모양으로 Firestore에 저장하도록
    짜여 있다. AI 응답 구조를 백엔드가 다시 풀어헤치게 하면 매핑 코드가
    백엔드에 생기고, 그 코드는 AI 스키마가 바뀔 때마다 같이 깨진다. 변환을
    AI 쪽에 두면 고칠 자리가 여기 하나로 남는다.
    """

    # --- 백엔드 SessionResultRequest 와 1:1 ---
    #: **Firestore `card` 컬렉션의 `type` 이다.** 백엔드 `collect_card()` 가
    #: `card` 에서 `type == detectedClass` 로 카드를 찾아 학생 도감에 등록한다.
    #: 그래서 클래스(pet/can/…)가 아니라 품목 단위 카드 type 을 싣는다.
    detected_class: str = Field(alias="detectedClass")
    confidence: float = Field(ge=0.0, le=1.0)
    needs_action: bool = Field(alias="needsAction")
    #: 아이에게 보여줄 한글 라벨. 명세서 §3 예시가 한글 문자열이다.
    actions: list[str] = Field(default_factory=list)
    disposal_category: str = Field(alias="disposalCategory")
    feedback_text: str = Field(alias="feedbackText")

    # --- 부가 정보. 백엔드가 필요할 때만 읽으면 된다 ---
    #: **After 비교에 반드시 필요하다.** 백엔드가 세션 문서에 저장해두고
    #: 재촬영 때 `beforeAnalysisId` 로 되돌려줘야 개선 여부를 계산할 수 있다.
    analysis_id: str = Field(alias="analysisId")
    #: 미션·뱃지 판정용 행동 코드. 명세서 §2가 "백엔드는 이 코드로 미션과
    #: 뱃지를 판정한다"고 못박은 그 코드다. actions(한글)와 순서가 같다.
    action_codes: list[str] = Field(default_factory=list, alias="actionCodes")
    #: AI 7종 클래스(pet/plastic/can/glass/pack/paper/vinyl). detectedClass가
    #: 품목 단위로 바뀌면서 클래스 정보가 사라지지 않게 따로 싣는다.
    #: 도감 카드의 `class` 필드와는 어휘가 다르다 — 카드는 general·battery를
    #: 쓰고 glass가 없다.
    class_code: str = Field(default="", alias="classCode")
    #: AI 원본 상태. 백엔드 3종(ACTION_REQUIRED/COMPLETED/CREATED)으로는
    #: 표현되지 않는 IMPROVED·PARTIALLY_IMPROVED·REJECTED 등이 그대로 실린다.
    ai_status: AnalysisStatus = Field(alias="aiStatus")
    #: AFTER 단계에서만 채워진다. 개선을 모두 해냈는지.
    improved: bool | None = None
    #: AFTER 단계에서 아직 남은 행동 (한글 라벨 / 코드).
    remaining_actions: list[str] = Field(default_factory=list, alias="remainingActions")
    remaining_action_codes: list[str] = Field(
        default_factory=list, alias="remainingActionCodes"
    )
    #: 판정을 거부·실패한 경우. 프론트가 retryable로 재촬영 안내와 중단
    #: 안내를 갈라야 한다. (명세서 §6)
    error: AnalysisError | None = None


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
