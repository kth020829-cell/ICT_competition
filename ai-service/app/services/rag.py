"""배출 기준 조회 — 지시서 §6 파이프라인 9단계, STEP 5.

`recycling_rules.json`(충북·청주 기준)에서 품목을 찾아 **배출 결론과 남은 행동**을
계산한다.

> **라우팅 키는 VLM이 판정한 품목명이다.** YOLO 클래스가 아니다. (지시서 §11-3)

같은 `pet` 클래스라도 투명 페트병은 뚜껑을 닫아서, 플라스틱 음료병은 뚜껑을 분리해서
배출한다. 클래스로 라우팅하면 둘 중 하나는 반드시 틀린 안내가 나간다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache

from app.core.config import get_settings
from app.schemas.enums import (
    ACTION_LABEL_KO,
    DISPOSAL_NAME_KO,
    ActionCode,
    DisposalCategory,
    StateValue,
)

logger = logging.getLogger(__name__)

#: 상태값이 이것들이면 행동을 요구하지 않는다.
#:
#: 판정하지 못한 것을 아이의 숙제로 떠넘기지 않는다는 뜻이다. 우유팩의 `rinsed`
#: 처럼 사진으로 확인이 어려운 상태를 `no`로 단정해 버리면, 이미 깨끗이 헹군
#: 아이에게 다시 헹구라고 시키게 된다.
_NO_ACTION_VALUES = {StateValue.UNKNOWN, StateValue.NOT_APPLICABLE}


@dataclass(frozen=True)
class Resolution:
    """품목 하나에 대한 배출 결론."""

    item_name_ko: str
    rule_id: str
    disposal: DisposalCategory
    disposal_name_ko: str
    required_actions: list[ActionCode] = field(default_factory=list)
    child_hint: str = ""
    safety_note: str | None = None
    #: 사진으로 판정할 수 없어 사용자 선택이 필요한 경우의 질문. (지시서 §4.4 아이스팩)
    user_choice_question: str | None = None

    @property
    def is_ready(self) -> bool:
        """남은 행동이 없으면 배출 준비 완료."""
        return not self.required_actions


class RulesNotFoundError(FileNotFoundError):
    """배출 기준 파일이 없다."""


@lru_cache(maxsize=1)
def _rules() -> dict:
    settings = get_settings()
    path = settings.rules_path
    if not path.exists():
        raise RulesNotFoundError(f"배출 기준 파일이 없습니다: {path}")
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def rule_version() -> str:
    return str(_rules().get("version", "unknown"))


def known_items() -> set[str]:
    return set(_rules().get("items", {}))


def _matches(condition: dict, states: dict[str, StateValue]) -> bool:
    """조건의 모든 키가 현재 상태와 일치하는지."""
    for key, expected in condition.items():
        if states.get(key) != expected:
            return False
    return True


def _collect_actions(rule: dict, states: dict[str, StateValue]) -> list[ActionCode]:
    """상태에서 남은 행동을 뽑아낸다. 순서는 규칙 파일의 기재 순서를 따른다."""
    codes: list[ActionCode] = []

    for code in rule.get("alwaysActions", []):
        codes.append(ActionCode(code))

    for state_key, triggers in (rule.get("stateActions") or {}).items():
        value = states.get(state_key)
        if value is None or value in _NO_ACTION_VALUES:
            continue
        code = triggers.get(str(value))
        if code:
            codes.append(ActionCode(code))

    # 특정 행동이 필요할 때만 따라붙는 안전 행동. (예: 캔을 누를 때 어른과 함께)
    for trigger, extras in (rule.get("safetyActions") or {}).items():
        if ActionCode(trigger) in codes:
            codes.extend(ActionCode(e) for e in extras)

    # 중복 제거하되 순서는 유지한다. 미션 카드가 뜨는 순서가 곧 행동 순서다.
    seen: set[ActionCode] = set()
    ordered: list[ActionCode] = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def _resolve_disposal(
    rule: dict, states: dict[str, StateValue]
) -> tuple[DisposalCategory, str]:
    """기본 배출 분류에 조건부 규칙을 적용한다."""
    disposal = DisposalCategory(rule["disposal"])
    rule_id = str(rule["ruleId"])

    for condition in rule.get("conditionalDisposal", []):
        if _matches(condition.get("when", {}), states):
            disposal = DisposalCategory(condition["disposal"])
            rule_id = str(condition.get("ruleId", rule_id))
            logger.debug("조건부 배출 적용: %s → %s", rule["ruleId"], rule_id)
            break

    return disposal, rule_id


def resolve(
    item_name_ko: str,
    states: dict[str, StateValue],
    *,
    user_choice: str | None = None,
) -> Resolution | None:
    """품목명과 상태로 배출 결론을 만든다.

    도감에 없는 품목이면 None. 호출부는 이를 NOT_WASTE 로 처리한다.
    """
    rule = _rules().get("items", {}).get(item_name_ko)
    if rule is None:
        logger.info("배출 기준에 없는 품목: %s", item_name_ko)
        return None

    # 사진으로 판정 불가한 품목은 사용자 선택으로 분기한다. (지시서 §4.4)
    choice_spec = rule.get("userChoice")
    if choice_spec:
        option = (choice_spec.get("options") or {}).get(user_choice or "")
        if option is None:
            # 아직 선택 전이다. 질문을 돌려주고 결론은 보류한다.
            return Resolution(
                item_name_ko=item_name_ko,
                rule_id=str(rule["ruleId"]),
                disposal=DisposalCategory(rule["disposal"]),
                disposal_name_ko=DISPOSAL_NAME_KO[DisposalCategory(rule["disposal"])],
                required_actions=[],
                child_hint=str(rule.get("childHint", "")),
                safety_note=rule.get("safetyNote"),
                user_choice_question=str(choice_spec.get("question", "")),
            )
        disposal = DisposalCategory(option["disposal"])
        return Resolution(
            item_name_ko=item_name_ko,
            rule_id=str(option.get("ruleId", rule["ruleId"])),
            disposal=disposal,
            disposal_name_ko=DISPOSAL_NAME_KO[disposal],
            required_actions=[ActionCode(c) for c in option.get("actions", [])],
            child_hint=str(option.get("childHint", rule.get("childHint", ""))),
            safety_note=rule.get("safetyNote"),
        )

    disposal, rule_id = _resolve_disposal(rule, states)
    return Resolution(
        item_name_ko=item_name_ko,
        rule_id=rule_id,
        disposal=disposal,
        disposal_name_ko=DISPOSAL_NAME_KO[disposal],
        required_actions=_collect_actions(rule, states),
        child_hint=str(rule.get("childHint", "")),
        safety_note=rule.get("safetyNote"),
    )


def action_label(code: ActionCode) -> str:
    return ACTION_LABEL_KO[code]
