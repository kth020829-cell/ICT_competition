"""Before/After 비교 — 지시서 §6 파이프라인 11단계, §4.2, STEP 8.

> After를 절대 기준으로 심판하지 말고 Before와 비교한다.

이 원칙이 이 모듈의 전부다. After 사진만 놓고 "아직 완벽하지 않다"고 판정하면
아이는 무엇을 해냈는지 알 수 없다. Before에서 요구했던 행동 중 무엇이 사라졌는지를
본다. 사라진 행동이 곧 아이가 해낸 일이다.
"""

from __future__ import annotations

import logging

from app.schemas.enums import ActionCode, AnalysisStatus
from app.schemas.response import Comparison
from app.services.analysis_store import Snapshot

logger = logging.getLogger(__name__)


def compare(
    before: Snapshot,
    *,
    after_item_name_ko: str | None,
    after_class_code: str | None,
    after_required_actions: list[ActionCode],
) -> Comparison:
    """Before에서 요구한 행동과 After에 남은 행동을 견준다."""
    before_set = set(before.required_actions)
    after_set = set(after_required_actions)

    # 같은 물건인지는 **클래스**로 본다. 품목명으로 보면 안 된다.
    #
    # 실측에서 나온 사례: 같은 페트병을 라벨이 붙은 채 찍으면 색이 있어 보여
    # '플라스틱 음료병', 라벨을 떼면 속이 비쳐 '투명 페트병'으로 판정된다.
    # 품목명으로 비교하면 아이가 시킨 대로 라벨을 뗀 순간 CLASS_MISMATCH가 나서
    # 해낸 일이 거부당한다. 클래스가 같으면 같은 물건으로 본다.
    same_class = (
        before.class_code is not None
        and after_class_code is not None
        and before.class_code == after_class_code
    )

    if same_class and before.item_name_ko != after_item_name_ko:
        logger.info(
            "같은 클래스 안에서 품목 판정이 바뀜: %s → %s (준비 행동으로 외형이 달라진 경우)",
            before.item_name_ko,
            after_item_name_ko,
        )

    # Before 순서를 유지한다. 아이가 안내받은 순서 그대로 되돌려줘야 읽힌다.
    improved = [a for a in before.required_actions if a not in after_set]
    remaining = [a for a in after_required_actions if a in before_set]
    regressed = [a for a in after_required_actions if a not in before_set]

    return Comparison(
        sameClass=same_class,
        expectedClass=before.class_code,
        detectedClass=after_class_code,
        improvedActions=improved,
        remainingActions=remaining,
        regressedActions=regressed,
    )


def status_for(comparison: Comparison) -> AnalysisStatus:
    """비교 결과를 상태로 옮긴다.

    남은 행동이 없으면 IMPROVED다. Before에 요구가 없었던 경우(이미 준비된
    물건을 다시 찍은 경우)도 여기 들어오는데, 아이 입장에서는 "다 됐다"가 맞다.
    """
    if not comparison.remaining_actions and not comparison.regressed_actions:
        return AnalysisStatus.IMPROVED
    if comparison.improved_actions:
        return AnalysisStatus.PARTIALLY_IMPROVED
    return AnalysisStatus.NOT_IMPROVED


def reward_eligible(comparison: Comparison) -> bool:
    """보상 자격 **참고값**. 실제 지급은 백엔드가 결정한다. (지시서 §5.6)"""
    return (
        comparison.same_class
        and not comparison.remaining_actions
        and not comparison.regressed_actions
    )
