"""AI 응답 → 백엔드 세션 result 양식 변환 (명세서 §3).

백엔드는 판정 결과를 평평한 6개 필드로 저장하게 짜여 있다. AI 응답은 중첩
구조다. 그 간극을 백엔드에 매핑 코드로 만들면 AI 스키마가 바뀔 때마다 백엔드가
같이 깨진다. 변환을 AI 쪽에 두는 이유가 그거다.

**의도적으로 잃는 것이 있다.** 백엔드 양식에는 `states`, `boundingBox`,
`processing` 자리가 없다. 그 값들이 필요해지면 `/v1/analyze` 를 쓰면 된다.
여기서는 백엔드가 지금 저장하는 것만 채운다.
"""

from __future__ import annotations

import logging

from app.schemas.enums import ACTION_LABEL_KO, AnalysisStatus
from app.schemas.response import AnalyzeResponse, SessionResult

logger = logging.getLogger(__name__)

#: After 단계에서 "개선을 다 해냈다"로 볼 상태.
_IMPROVED_STATUSES = {AnalysisStatus.IMPROVED, AnalysisStatus.COMPLETED}

#: 판정이 성립하지 않은 상태. 품목·배출 분류가 없다.
_FAILED_STATUSES = {AnalysisStatus.REJECTED, AnalysisStatus.FAILED}


def to_session_result(response: AnalyzeResponse) -> SessionResult:
    """AnalyzeResponse를 백엔드 세션 result 양식으로 옮긴다."""

    detection = response.detection
    disposal = response.disposal

    # --- 거부·실패: 품목이 없다 ---
    #
    # 백엔드 모델은 detectedClass / disposalCategory 를 필수 문자열로 받는다.
    # None을 넣을 자리가 없으므로 빈 문자열로 낸다. needsAction은 True로 둔다 —
    # 백엔드가 `if needsAction: ACTION_REQUIRED` 로 상태를 정하므로, 그래야
    # 아이에게 재촬영을 안내하는 화면으로 간다.
    if response.status in _FAILED_STATUSES:
        message = response.feedback.message
        if response.error and response.error.message_ko:
            message = response.error.message_ko

        return SessionResult(
            detectedClass="",
            confidence=0.0,
            needsAction=True,
            actions=[],
            disposalCategory="",
            feedbackText=message,
            analysisId=response.analysis_id,
            actionCodes=[],
            aiStatus=response.status,
            error=response.error,
        )

    # --- AFTER: 남은 행동만 안내한다 ---
    #
    # Before에서 요구했던 행동을 그대로 다시 내면 아이가 해낸 일이 지워진다.
    # 비교 결과의 remainingActions 만 남긴다. (지시서 §4.2)
    if response.comparison is not None:
        remaining_codes = [str(c) for c in response.comparison.remaining_actions]
        remaining_labels = _labels(remaining_codes)

        return SessionResult(
            detectedClass=detection.class_code or "",
            confidence=detection.confidence,
            needsAction=bool(remaining_codes),
            actions=remaining_labels,
            disposalCategory=(str(disposal.category_code) if disposal else ""),
            feedbackText=response.feedback.message,
            analysisId=response.analysis_id,
            actionCodes=remaining_codes,
            aiStatus=response.status,
            improved=response.status in _IMPROVED_STATUSES,
            remainingActions=remaining_labels,
            remainingActionCodes=remaining_codes,
            error=response.error,
        )

    # --- BEFORE / SINGLE ---
    codes = [str(a.code) for a in response.required_actions]

    return SessionResult(
        detectedClass=detection.class_code or "",
        confidence=detection.confidence,
        needsAction=bool(codes),
        # label_ko 가 이미 응답에 실려 있으므로 그걸 쓴다. 표를 다시 뒤지면
        # 프롬프트가 문구를 바꿀 때 두 곳이 어긋난다.
        actions=[a.label_ko for a in response.required_actions],
        disposalCategory=(str(disposal.category_code) if disposal else ""),
        feedbackText=response.feedback.message,
        analysisId=response.analysis_id,
        actionCodes=codes,
        aiStatus=response.status,
        error=response.error,
    )


def _labels(codes: list[str]) -> list[str]:
    """행동 코드를 한글 라벨로 옮긴다.

    비교 결과에는 코드만 실려 오므로 표를 참조한다. 표에 없는 코드는 코드를
    그대로 내보낸다 — 조용히 빠뜨리면 아이가 해야 할 행동 하나가 화면에서
    사라진다.
    """
    labels = []
    for code in codes:
        label = ACTION_LABEL_KO.get(code)
        if label is None:
            logger.warning("한글 라벨이 없는 행동 코드: %r", code)
            label = code
        labels.append(label)
    return labels
