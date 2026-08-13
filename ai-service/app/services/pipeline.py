"""파이프라인 조립 — 지시서 §6.

     1. 이미지 수신
     2. EXIF 회전 보정          ┐
     3. 메타데이터 제거          ├ preprocess.py
     4. 품질 검사               ┘
     5. 얼굴 검출               ← safety.py
     6. YOLO 추론               ← detector.py
     7. 크롭 + 원본 폐기         ← cropper.py
     8. VLM 상태 판정           ← state_analyzer.py
     9. RAG 배출 기준 결합       ← rag.py
    10. 아동 언어 피드백 생성    ← feedback.py
    11. Before/After 비교       ← before_after.py

**라우팅은 VLM이 판정한 품목명으로 한다.** YOLO 클래스는 크롭할 박스를 정하고
프롬프트를 고르는 힌트일 뿐이다. `pack` 클래스 mAP50이 0.310이라 클래스를
결정으로 쓰면 그대로 서비스 오류가 된다. (지시서 §1, §11-3)

캐시 조회는 지시서에서 7단계(YOLO 다음)지만 여기서는 **맨 앞**에서 한다.
키가 원본 이미지 해시라 앞에서 봐도 결과가 같고, 전처리·얼굴 검출·YOLO까지
통째로 건너뛸 수 있다. (cache.py)
"""

from __future__ import annotations

import logging
import time

from PIL import Image

from app.core.config import get_settings
from app.core.ids import new_analysis_id
from app.schemas.enums import (
    ACTION_LABEL_KO,
    CLASS_NAME_KO,
    ERROR_RETRYABLE,
    ActionCode,
    AnalysisStatus,
    DetectionSource,
    ErrorCode,
    Phase,
    StateValue,
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
from app.services import (
    analysis_store,
    before_after,
    cache,
    cropper,
    detector,
    feedback,
    preprocess,
    rag,
    safety,
    state_analyzer,
)
from app.services.analysis_store import Snapshot
from app.services.preprocess import ImageDecodeError
from app.services.state_analyzer import StateJudgement, VlmError

logger = logging.getLogger(__name__)

#: 품질 미달 시 아이에게 보여줄 문구. 원인마다 다른 행동을 요구해야 교정이 된다.
_QUALITY_FEEDBACK: dict[ErrorCode, tuple[str, str]] = {
    ErrorCode.IMAGE_TOO_DARK: ("조금 어두워", "불을 켜거나 밝은 곳에서 다시 찍어줄래?"),
    ErrorCode.IMAGE_TOO_BLURRY: ("사진이 흔들렸어", "손을 잠깐 멈추고 다시 찍어줄래?"),
}


def _processing(started: float, *, used_vlm: bool = False, cache_hit: bool = False) -> Processing:
    settings = get_settings()
    return Processing(
        usedVlm=used_vlm,
        cacheHit=cache_hit,
        elapsedMs=int((time.perf_counter() - started) * 1000),
        modelVersion=settings.model_version,
        promptVersion=settings.prompt_version,
        ruleVersion=settings.rule_version,
    )


def _reject(
    req: AnalyzeRequest,
    code: ErrorCode,
    title: str,
    message: str,
    started: float,
    *,
    face_detected: bool = False,
    is_waste_image: bool = True,
    status: AnalysisStatus = AnalysisStatus.REJECTED,
    used_vlm: bool = False,
) -> AnalyzeResponse:
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
        feedback=feedback.simple(title, message),
        error=AnalysisError(code=code, messageKo=message, retryable=ERROR_RETRYABLE[code]),
        processing=_processing(started, used_vlm=used_vlm),
    )


def _state_items(judgement: StateJudgement) -> dict[str, StateItem]:
    return {
        key: StateItem(value=value, confidence=round(conf, 4))
        for key, (value, conf) in judgement.states.items()
    }


def _plain_states(judgement: StateJudgement) -> dict[str, StateValue]:
    """규칙 조회용. 신뢰도를 떼고 값만 남긴다."""
    return {key: value for key, (value, _) in judgement.states.items()}


def _required_actions(codes: list[ActionCode]) -> list[RequiredAction]:
    return [
        RequiredAction(code=code, labelKo=ACTION_LABEL_KO[code], required=True)
        for code in codes
    ]


def _rehydrate(response: AnalyzeResponse, req: AnalyzeRequest, started: float) -> AnalyzeResponse:
    """캐시에서 꺼낸 응답을 이번 요청의 것으로 만든다.

    `analysisId` 는 새로 발급한다. 분석 한 번에 하나씩 붙는 식별자이고, 백엔드가
    이걸로 Before/After를 잇는다. 캐시에 박힌 옛 id를 그대로 돌려주면 서로 다른
    스캔이 같은 id를 갖게 된다.

    같은 이유로 비교용 스냅샷도 다시 넣어준다. 캐시는 디스크에 남지만
    `analysis_store` 는 메모리라 서버를 다시 켜면 비어 있다.
    """
    response = response.model_copy(deep=True)
    response.analysis_id = new_analysis_id()
    response.scan_session_id = req.scan_session_id
    response.processing.cache_hit = True
    # 이번 요청은 VLM을 부르지 않았다. 판정 자체는 예전에 VLM이 만든 것이지만,
    # 백엔드는 이 값으로 호출 비용을 집계하므로 '이번에 불렀는가'를 담아야 한다.
    response.processing.used_vlm = False
    response.processing.elapsed_ms = int((time.perf_counter() - started) * 1000)

    if response.detection.item_name_ko:
        analysis_store.save(
            Snapshot(
                analysis_id=response.analysis_id,
                scan_session_id=req.scan_session_id,
                item_name_ko=response.detection.item_name_ko,
                class_code=response.detection.class_code,
                states={k: StateValue(v.value) for k, v in response.states.items()},
                required_actions=[a.code for a in response.required_actions],
            )
        )
    return response


def run(payload: bytes, req: AnalyzeRequest) -> AnalyzeResponse:
    """이미지 한 장을 처리한다. 캐시를 먼저 보고, 없으면 파이프라인을 돈다."""
    settings = get_settings()
    started = time.perf_counter()

    use_cache = settings.cache_enabled or settings.ai_mode == "cached"
    if use_cache:
        hit = cache.get(payload, req)
        if hit is not None:
            logger.info("캐시 적중 — VLM 호출 없음 (%s)", req.phase)
            return _rehydrate(hit, req, started)

    if settings.ai_mode == "cached":
        # 오프라인 전용 모드인데 캐시에 없다. 네트워크를 쓰지 않는 것이 이 모드의
        # 약속이므로 VLM으로 넘어가지 않고 여기서 멈춘다.
        logger.warning("cached 모드인데 캐시에 없는 사진이다.")
        return _reject(
            req,
            ErrorCode.VLM_UNAVAILABLE,
            "지금은 새 사진을 볼 수 없어",
            "미리 준비해 둔 사진으로 다시 해볼래?",
            started,
            status=AnalysisStatus.FAILED,
        )

    response = _run_pipeline(payload, req, started)
    if use_cache:
        cache.put(payload, req, response)
    return response


def _run_pipeline(payload: bytes, req: AnalyzeRequest, started: float) -> AnalyzeResponse:
    """업로드 이미지 한 장을 파이프라인 전 구간에 태운다."""

    # --- 2~4단계: 전처리 ---------------------------------------------------
    try:
        prepared = preprocess.prepare(payload)
    except ImageDecodeError as exc:
        logger.warning("이미지 디코딩 실패: %s", exc)
        return _reject(
            req,
            ErrorCode.INVALID_AI_OUTPUT,
            "사진을 읽지 못했어",
            "다른 사진으로 다시 시도해줄래?",
            started,
            status=AnalysisStatus.FAILED,
        )

    if not prepared.quality.ok:
        code = prepared.quality.error_code
        title, message = _QUALITY_FEEDBACK[code]
        logger.info(
            "품질 미달 %s (blur=%.1f brightness=%.1f)",
            code,
            prepared.quality.blur_score,
            prepared.quality.brightness,
        )
        return _reject(req, code, title, message, started)

    # --- 5단계: 얼굴 검출 --------------------------------------------------
    # 크롭보다 먼저 본다. 크롭이 얼굴을 잘라내면 얼굴이 찍혔다는 사실을 놓친다.
    face = safety.detect_faces(prepared.image)
    if face.has_face:
        return _reject(
            req,
            ErrorCode.FACE_DETECTED,
            "얼굴이 같이 찍혔어",
            "쓰레기만 나오게 다시 찍어줄래?",
            started,
            face_detected=True,
        )

    # --- 6단계: YOLO 추론 --------------------------------------------------
    result = detector.detect(prepared.image)

    if result.multiple_objects:
        return _reject(
            req,
            ErrorCode.MULTIPLE_OBJECTS,
            "물건이 여러 개야",
            "하나만 골라서 찍어줄래?",
            started,
        )

    # --- 7단계: 크롭 후 원본 즉시 폐기 (지시서 §11-5) ----------------------
    box: BoundingBox | None = None
    yolo_confidence = 0.0
    source = DetectionSource.VLM_ONLY
    class_hint: str | None = req.expected_class

    if result.has_crop_target:
        best = result.best
        # 이 줄 이후 배경이 포함된 원본은 남지 않는다.
        vlm_image: Image.Image = cropper.crop_and_discard(prepared.image, best.box)
        box = BoundingBox(
            x=round(best.box.x, 4),
            y=round(best.box.y, 4),
            width=round(best.box.width, 4),
            height=round(best.box.height, 4),
        )
        yolo_confidence = round(best.confidence, 4)
        source = DetectionSource.YOLO
        class_hint = best.class_code
    else:
        # 폴백 경로 — 미검출 또는 저신뢰도. 원본 전체를 VLM에 넘긴다.
        # 한계가 아니라 연산 절약 설계다. (지시서 §3)
        logger.info("검출 없음 → VLM 단독 경로")
        vlm_image = prepared.image

    # --- 8단계: VLM 상태 판정 ----------------------------------------------
    try:
        judgement = state_analyzer.analyze(vlm_image, class_hint=class_hint)
    except VlmError as exc:
        logger.warning("VLM 판정 실패: %s (%s)", exc, exc.code)
        title, message = (
            ("잠깐 생각이 길어졌어", "다시 한 번만 찍어줄래?")
            if exc.code == ErrorCode.AI_TIMEOUT
            else ("지금은 판정을 못 하겠어", "잠시 뒤에 다시 시도해줄래?")
        )
        return _reject(
            req, exc.code, title, message, started,
            status=AnalysisStatus.FAILED, used_vlm=True,
        )

    if not judgement.is_waste or judgement.item_name_ko is None:
        return _reject(
            req,
            ErrorCode.NOT_WASTE,
            "무엇인지 모르겠어",
            "분리배출할 물건을 가까이서 찍어줄래?",
            started,
            is_waste_image=judgement.is_waste,
            used_vlm=True,
        )

    # --- 9단계: RAG 배출 기준 결합 -----------------------------------------
    resolution = rag.resolve(
        judgement.item_name_ko,
        _plain_states(judgement),
        user_choice=req.user_choice,
    )
    if resolution is None:
        # 도감에 없는 품목. VLM enum이 막아주므로 보통 오지 않는다.
        return _reject(
            req,
            ErrorCode.NOT_WASTE,
            "아직 모르는 물건이야",
            "도감에 있는 물건을 찍어줄래?",
            started,
            used_vlm=True,
        )

    detection = Detection(
        # 최종 클래스는 VLM 판정 품목에서 나온다. YOLO 클래스가 아니다. (§11-3)
        classCode=judgement.class_code,
        classNameKo=CLASS_NAME_KO.get(judgement.class_code) if judgement.class_code else None,
        itemNameKo=judgement.item_name_ko,
        # 신뢰도는 '박스를 얼마나 확신했나'이므로 YOLO 값을 그대로 싣는다.
        confidence=yolo_confidence,
        source=source,
        boundingBox=box,
    )

    # --- 11단계: Before/After 비교 ------------------------------------------
    comparison: Comparison | None = None
    reward: bool | None = None
    status: AnalysisStatus

    if req.phase == Phase.AFTER and req.before_analysis_id:
        snapshot = analysis_store.get(req.before_analysis_id)
        if snapshot is None:
            logger.info("Before 분석을 찾지 못함: %s → 단독 판정", req.before_analysis_id)
            status = (
                AnalysisStatus.COMPLETED
                if resolution.is_ready
                else AnalysisStatus.ACTION_REQUIRED
            )
        else:
            comparison = before_after.compare(
                snapshot,
                after_item_name_ko=judgement.item_name_ko,
                after_class_code=judgement.class_code,
                after_required_actions=resolution.required_actions,
            )
            if not comparison.same_class:
                # 다른 물건을 찍었다. 비교는 무의미하므로 재촬영을 요청한다.
                return _reject(
                    req,
                    ErrorCode.CLASS_MISMATCH,
                    "아까와 다른 물건이야",
                    "처음에 찍었던 물건을 다시 찍어줄래?",
                    started,
                    used_vlm=True,
                )
            status = before_after.status_for(comparison)
            reward = before_after.reward_eligible(comparison)
    else:
        status = (
            AnalysisStatus.COMPLETED if resolution.is_ready else AnalysisStatus.ACTION_REQUIRED
        )
        if req.phase != Phase.AFTER:
            reward = resolution.is_ready

    # --- 10단계: 아동 언어 피드백 -------------------------------------------
    message = feedback.build(
        status,
        vlm_message=judgement.child_message,
        resolution=resolution,
        item_name_ko=judgement.item_name_ko,
    )

    analysis_id = new_analysis_id()

    # 판정을 남겨 이후 비교에 쓴다. 이미지는 저장하지 않는다. (지시서 §11-5)
    # Before뿐 아니라 After도 남긴다. 백엔드가 /v1/compare 로 보상 판정을
    # 다시 계산할 때 두 분석이 모두 필요하기 때문이다. (지시서 §5.6)
    analysis_store.save(
        Snapshot(
            analysis_id=analysis_id,
            scan_session_id=req.scan_session_id,
            item_name_ko=judgement.item_name_ko,
            class_code=judgement.class_code,
            states=_plain_states(judgement),
            required_actions=list(resolution.required_actions),
        )
    )

    return AnalyzeResponse(
        analysisId=analysis_id,
        scanSessionId=req.scan_session_id,
        phase=req.phase,
        status=status,
        safety=Safety(faceDetected=False, isWasteImage=True),
        detection=detection,
        states=_state_items(judgement),
        requiredActions=_required_actions(resolution.required_actions),
        disposal=Disposal(
            categoryCode=resolution.disposal,
            categoryNameKo=resolution.disposal_name_ko,
            ruleId=resolution.rule_id,
        ),
        feedback=message,
        comparison=comparison,
        rewardEligible=reward,
        processing=_processing(started, used_vlm=True),
    )
