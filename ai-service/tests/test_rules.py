"""STEP 5 — 배출 기준 조회·피드백 단위 테스트.

VLM을 부르지 않는 순수 로직만 여기에 둔다. 규칙 파일이 곧 서비스의 정답표라
데이터 자체의 무결성도 함께 검사한다.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import get_settings
from app.schemas.enums import (
    ITEM_TO_CLASS,
    ActionCode,
    AnalysisStatus,
    DisposalCategory,
    StateValue,
)
from app.services import feedback, rag


# --------------------------------------------------------------------------
# 규칙 데이터 무결성
# --------------------------------------------------------------------------
def test_rules_cover_every_item_in_the_catalog():
    """도감 품목이 규칙에 하나도 빠지면 안 된다. 빠지면 그 품목은 NOT_WASTE가 된다."""
    assert rag.known_items() == set(ITEM_TO_CLASS)


def test_rule_class_codes_match_the_catalog():
    with get_settings().rules_path.open(encoding="utf-8") as fp:
        items = json.load(fp)["items"]
    for name, rule in items.items():
        assert rule.get("classCode") == ITEM_TO_CLASS[name], name


def test_rule_codes_are_valid_enum_values():
    with get_settings().rules_path.open(encoding="utf-8") as fp:
        items = json.load(fp)["items"]
    for name, rule in items.items():
        DisposalCategory(rule["disposal"])  # 잘못된 값이면 ValueError
        for triggers in (rule.get("stateActions") or {}).values():
            for code in triggers.values():
                ActionCode(code), name
        for extras in (rule.get("safetyActions") or {}).values():
            for code in extras:
                ActionCode(code), name


# --------------------------------------------------------------------------
# 품목별 분기 — 같은 클래스인데 결론이 다른 경우
# --------------------------------------------------------------------------
def test_clear_pet_keeps_its_cap_but_colored_bottle_removes_it():
    """지시서 §4.4 — 투명 페트병은 뚜껑을 닫아서, 유색 병은 분리해서 배출한다.

    같은 `pet` 클래스라 클래스로 라우팅하면 둘 중 하나는 반드시 틀린다. (§11-3)
    """
    states = {
        "labelAttached": StateValue.NO,
        "capAttached": StateValue.YES,
        "contentRemaining": StateValue.NO,
        "flattened": StateValue.YES,
    }

    clear = rag.resolve("투명 페트병", states)
    assert clear.disposal == DisposalCategory.CLEAR_PET_BIN
    assert ActionCode.REMOVE_CAP not in clear.required_actions
    assert clear.is_ready

    colored = rag.resolve("플라스틱 음료병", states)
    assert colored.disposal == DisposalCategory.PLASTIC_BIN
    assert ActionCode.REMOVE_CAP in colored.required_actions
    assert not colored.is_ready


def test_receipt_is_always_general_waste():
    """지시서 §4.4 — 영수증은 감열지로 간주하며 상태와 무관하게 일반쓰레기다."""
    resolution = rag.resolve("영수증", {})
    assert resolution.disposal == DisposalCategory.GENERAL_WASTE
    assert resolution.required_actions == []


def test_box_only_cares_about_tape_not_folding():
    """지시서 §4.4 — 테이프만 본다. 접었는지는 판정 대상이 아니다."""
    taped = rag.resolve("택배상자", {"tapeAttached": StateValue.YES})
    assert taped.required_actions == [ActionCode.SEPARATE_MATERIALS]

    clean = rag.resolve("택배상자", {"tapeAttached": StateValue.NO})
    assert clean.required_actions == []
    assert clean.disposal == DisposalCategory.PAPER_BIN


def test_contaminated_container_falls_back_to_general_waste():
    dirty = rag.resolve(
        "배달 플라스틱 용기",
        {"contaminated": StateValue.YES, "contentRemaining": StateValue.NO},
    )
    assert dirty.disposal == DisposalCategory.GENERAL_WASTE
    assert ActionCode.RINSE in dirty.required_actions


def test_can_asks_for_an_adult_only_when_crushing():
    """지시서 §12 — 날카로운 캔 뚜껑은 어른과 함께."""
    needs_crush = rag.resolve("알루미늄캔", {"flattened": StateValue.NO})
    assert ActionCode.CRUSH in needs_crush.required_actions
    assert ActionCode.ASK_ADULT in needs_crush.required_actions

    done = rag.resolve("알루미늄캔", {"flattened": StateValue.YES})
    assert ActionCode.ASK_ADULT not in done.required_actions


# --------------------------------------------------------------------------
# unknown 정책
# --------------------------------------------------------------------------
def test_unknown_state_never_creates_a_chore():
    """판정하지 못한 것을 아이의 숙제로 떠넘기지 않는다.

    우유팩의 `rinsed`는 사진으로 확인이 어렵다. `no`로 단정하면 이미 깨끗이
    헹군 아이에게 다시 헹구라고 시키게 된다.
    """
    unknown = rag.resolve(
        "우유팩",
        {
            "contentRemaining": StateValue.NO,
            "rinsed": StateValue.UNKNOWN,
            "unfolded": StateValue.YES,
        },
    )
    assert ActionCode.RINSE not in unknown.required_actions
    assert unknown.is_ready

    known_dirty = rag.resolve(
        "우유팩",
        {
            "contentRemaining": StateValue.NO,
            "rinsed": StateValue.NO,
            "unfolded": StateValue.YES,
        },
    )
    assert ActionCode.RINSE in known_dirty.required_actions


def test_not_applicable_is_also_ignored():
    resolution = rag.resolve("유리병", {"capAttached": StateValue.NOT_APPLICABLE})
    assert ActionCode.REMOVE_CAP not in resolution.required_actions


def test_unknown_item_returns_none():
    assert rag.resolve("스티로폼 용기", {}) is None


# --------------------------------------------------------------------------
# 사용자 선택 분기 (지시서 §4.4 아이스팩)
# --------------------------------------------------------------------------
def test_ice_pack_asks_before_concluding():
    pending = rag.resolve("아이스팩", {})
    assert pending.user_choice_question
    assert pending.required_actions == []


def test_ice_pack_branches_on_user_choice():
    gel = rag.resolve("아이스팩", {}, user_choice="gel")
    assert gel.disposal == DisposalCategory.GENERAL_WASTE
    assert gel.user_choice_question is None

    water = rag.resolve("아이스팩", {}, user_choice="water")
    assert water.disposal == DisposalCategory.VINYL_BIN
    assert ActionCode.EMPTY_CONTENT in water.required_actions


# --------------------------------------------------------------------------
# 피드백 조립
# --------------------------------------------------------------------------
def test_disposal_location_is_withheld_until_ready():
    """남은 행동이 있는데 배출 장소를 알려주면 아이가 그냥 버리고 끝낸다."""
    pending = rag.resolve("투명 페트병", {"labelAttached": StateValue.YES})
    message = feedback.build(
        AnalysisStatus.ACTION_REQUIRED,
        vlm_message="라벨이 아직 붙어 있네.",
        resolution=pending,
        item_name_ko="투명 페트병",
    )
    assert "전용함" not in message.message
    assert "라벨 떼기" in message.message


def test_ready_item_gets_the_disposal_hint():
    ready = rag.resolve(
        "투명 페트병",
        {
            "labelAttached": StateValue.NO,
            "capAttached": StateValue.YES,
            "contentRemaining": StateValue.NO,
            "flattened": StateValue.YES,
        },
    )
    message = feedback.build(
        AnalysisStatus.COMPLETED, vlm_message="깨끗하게 준비됐구나.", resolution=ready
    )
    assert ready.child_hint in message.message


def test_tts_text_drops_symbols():
    message = feedback.simple("확인했어", "라벨을 떼줄래? **중요**")
    assert "*" not in message.tts_text
    assert "라벨을" in message.tts_text


def test_action_sentence_counts_the_remainder_correctly():
    """4개가 남았는데 '하나 더'라고 하면 아이가 헷갈린다."""
    many = rag.resolve(
        "플라스틱 음료병",
        {
            "labelAttached": StateValue.YES,
            "capAttached": StateValue.YES,
            "contentRemaining": StateValue.YES,
            "flattened": StateValue.NO,
        },
    )
    assert len(many.required_actions) == 4
    message = feedback.build(AnalysisStatus.ACTION_REQUIRED, resolution=many)
    assert "2개가 더 남았어" in message.message


@pytest.mark.parametrize("item", sorted(ITEM_TO_CLASS))
def test_every_item_resolves_without_error(item: str):
    """상태를 전혀 모를 때도 모든 품목이 결론을 낼 수 있어야 한다."""
    resolution = rag.resolve(item, {})
    assert resolution is not None
    assert resolution.rule_id
    assert resolution.disposal_name_ko


# --------------------------------------------------------------------------
# 프롬프트 ↔ 도감 동기화
# --------------------------------------------------------------------------
def test_prompt_lists_every_catalog_item():
    """기본 프롬프트에 도감 29종이 모두 적혀 있어야 한다.

    실측에서 확인된 문제 — YOLO 클래스 힌트로 고른 품목별 지침이 VLM의 시야를
    좁혔다. 캔 사진에 우유팩 지침이 붙자 '캔이 뜯겨 있다'고 보면서도 품목은
    '알 수 없음'으로 답했다. YOLO 클래스 정확도가 50%라 절반은 틀린 지침이
    들어간다. 그래서 기본 프롬프트에 전체 목록을 실어 항상 보이게 한다.
    """
    prompt = (get_settings().prompts_dir / "state_analysis.txt").read_text(encoding="utf-8")
    missing = [item for item in ITEM_TO_CLASS if item not in prompt]
    assert not missing, f"프롬프트에 빠진 품목: {missing}"


def test_prompt_warns_that_the_class_hint_is_unreliable():
    prompt = (get_settings().prompts_dir / "state_analysis.txt").read_text(encoding="utf-8")
    assert "절반쯤 틀립니다" in prompt
