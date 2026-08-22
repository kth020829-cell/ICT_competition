"""STEP 8 — Before/After 비교 단위 테스트.

지시서 §4.2 — After를 절대 기준으로 심판하지 말고 Before와 비교한다.
"""

from __future__ import annotations

from app.schemas.enums import ActionCode, AnalysisStatus, StateValue
from app.services import analysis_store, before_after
from app.services.analysis_store import Snapshot


def snapshot(*actions: ActionCode, item: str = "투명 페트병", class_code: str = "pet") -> Snapshot:
    return Snapshot(
        analysis_id="analysis_test",
        scan_session_id="scan_test",
        item_name_ko=item,
        class_code=class_code,
        states={},
        required_actions=list(actions),
    )


def test_completed_actions_count_as_improvements():
    comparison = before_after.compare(
        snapshot(ActionCode.REMOVE_LABEL, ActionCode.CRUSH),
        after_item_name_ko="투명 페트병",
        after_class_code="pet",
        after_required_actions=[ActionCode.CRUSH],
    )
    assert comparison.improved_actions == [ActionCode.REMOVE_LABEL]
    assert comparison.remaining_actions == [ActionCode.CRUSH]
    assert comparison.regressed_actions == []
    assert before_after.status_for(comparison) == AnalysisStatus.PARTIALLY_IMPROVED
    assert not before_after.reward_eligible(comparison)


def test_all_done_is_improved_and_reward_eligible():
    comparison = before_after.compare(
        snapshot(ActionCode.REMOVE_LABEL, ActionCode.CRUSH),
        after_item_name_ko="투명 페트병",
        after_class_code="pet",
        after_required_actions=[],
    )
    assert comparison.improved_actions == [ActionCode.REMOVE_LABEL, ActionCode.CRUSH]
    assert before_after.status_for(comparison) == AnalysisStatus.IMPROVED
    assert before_after.reward_eligible(comparison)


def test_nothing_changed_is_not_improved():
    comparison = before_after.compare(
        snapshot(ActionCode.CRUSH),
        after_item_name_ko="투명 페트병",
        after_class_code="pet",
        after_required_actions=[ActionCode.CRUSH],
    )
    assert comparison.improved_actions == []
    assert before_after.status_for(comparison) == AnalysisStatus.NOT_IMPROVED


def test_item_may_change_within_the_same_class():
    """실측 사례 — 라벨을 떼면 색이 드러나 품목 판정이 바뀐다.

    라벨이 붙어 있을 때는 색이 있어 보여 '플라스틱 음료병', 떼고 나면 속이 비쳐
    '투명 페트병'이 된다. 품목명으로 비교하면 아이가 시킨 대로 라벨을 뗀
    순간 CLASS_MISMATCH가 나서 해낸 일이 거부당한다.
    """
    comparison = before_after.compare(
        snapshot(ActionCode.REMOVE_LABEL, ActionCode.CRUSH, item="플라스틱 음료병"),
        after_item_name_ko="투명 페트병",
        after_class_code="pet",
        after_required_actions=[ActionCode.CRUSH],
    )
    assert comparison.same_class
    assert comparison.improved_actions == [ActionCode.REMOVE_LABEL]


def test_a_genuinely_different_object_is_a_mismatch():
    comparison = before_after.compare(
        snapshot(ActionCode.CRUSH),
        after_item_name_ko="택배상자",
        after_class_code="paper",
        after_required_actions=[],
    )
    assert not comparison.same_class
    assert not before_after.reward_eligible(comparison)


def test_new_problems_are_reported_as_regressions():
    comparison = before_after.compare(
        snapshot(ActionCode.REMOVE_LABEL),
        after_item_name_ko="투명 페트병",
        after_class_code="pet",
        after_required_actions=[ActionCode.EMPTY_CONTENT],
    )
    assert comparison.improved_actions == [ActionCode.REMOVE_LABEL]
    assert comparison.regressed_actions == [ActionCode.EMPTY_CONTENT]
    assert not before_after.reward_eligible(comparison)


# --------------------------------------------------------------------------
# 저장소
# --------------------------------------------------------------------------
def test_store_round_trip():
    analysis_store.clear()
    snap = Snapshot(
        analysis_id="analysis_abc",
        scan_session_id="scan_1",
        item_name_ko="투명 페트병",
        class_code="pet",
        states={"labelAttached": StateValue.YES},
        required_actions=[ActionCode.REMOVE_LABEL],
    )
    analysis_store.save(snap)
    assert analysis_store.get("analysis_abc").item_name_ko == "투명 페트병"
    assert analysis_store.get("없는_id") is None


def test_store_keeps_no_pixels():
    """이미지를 저장하지 않는다는 것이 이 저장소의 계약이다. (지시서 §11-5)"""
    fields = set(Snapshot.__dataclass_fields__)
    assert not fields & {"image", "payload", "crop", "thumbnail"}
