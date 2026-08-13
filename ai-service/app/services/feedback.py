"""아동 언어 피드백 조립 — 지시서 §6 파이프라인 10단계, STEP 5.

VLM이 준 `childMessage`(지금 보이는 상태에 대한 말)와 규칙에서 온 안내
(배출 장소·안전 주의)를 하나의 문장으로 합친다.

**피드백 문구를 위해 VLM을 한 번 더 부르지 않는다.** 판정과 같은 호출에서
`childMessage`를 함께 받아오므로 비용과 지연이 늘지 않는다. 여기서는 규칙에서
나온 정보만 덧붙인다.

TTS 텍스트를 따로 만드는 이유는 이모지·기호가 그대로 읽히면 안 되기 때문이다.
"""

from __future__ import annotations

import re

from app.schemas.enums import ACTION_LABEL_KO, ActionCode, AnalysisStatus
from app.schemas.response import Feedback
from app.services.rag import Resolution

#: 상태별 제목. 아이가 가장 먼저 읽는 한 줄이다.
_TITLE: dict[str, str] = {
    AnalysisStatus.ACTION_REQUIRED: "조금만 더 준비하자",
    AnalysisStatus.COMPLETED: "완벽해!",
    AnalysisStatus.IMPROVED: "다 해냈어!",
    AnalysisStatus.PARTIALLY_IMPROVED: "좋아지고 있어!",
    AnalysisStatus.NOT_IMPROVED: "조금만 더 해볼까?",
}

#: TTS에서 걸러낼 문자. 이모지·장식 기호가 그대로 발음되면 아이가 혼란스럽다.
_TTS_STRIP = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF️"  # 이모지
    r"*_`#~\[\]()<>|]"  # 마크다운·장식 기호
)


def _tts(text: str) -> str:
    """발화용 텍스트. 기호를 걷어내고 공백을 정리한다."""
    return re.sub(r"\s+", " ", _TTS_STRIP.sub("", text)).strip()


def _action_sentence(actions: list[ActionCode]) -> str:
    """남은 행동을 한 문장으로. 세 개가 넘으면 앞의 둘만 말한다.

    한 번에 다 시키면 아이가 어디서부터 해야 할지 모른다.
    """
    if not actions:
        return ""
    labels = [ACTION_LABEL_KO[a] for a in actions]
    if len(labels) == 1:
        return f"{labels[0]}부터 해볼까?"
    if len(labels) == 2:
        return f"{labels[0]}하고 {labels[1]}를 해볼까?"
    return f"{labels[0]}하고 {labels[1]}부터 해볼까? 그다음에 {len(labels) - 2}개가 더 남았어."


def build(
    status: AnalysisStatus,
    *,
    vlm_message: str = "",
    resolution: Resolution | None = None,
    item_name_ko: str | None = None,
) -> Feedback:
    """상태 + VLM 문장 + 규칙 안내를 합쳐 최종 피드백을 만든다."""
    title = _TITLE.get(status, "확인했어")
    if status == AnalysisStatus.ACTION_REQUIRED and item_name_ko:
        title = f"{item_name_ko}을(를) 찾았어!"

    parts: list[str] = []

    if vlm_message:
        parts.append(vlm_message)

    if resolution is not None:
        # 사용자 선택이 필요한 품목은 결론 대신 질문을 던진다.
        if resolution.user_choice_question:
            parts.append(resolution.user_choice_question)
        elif resolution.is_ready:
            # 준비가 끝났을 때만 배출 장소를 말한다. 남은 행동이 있는데
            # 어디에 버리라고 하면 아이가 그냥 버리고 끝낸다.
            if resolution.child_hint:
                parts.append(resolution.child_hint)
        else:
            # 다음 행동은 **항상 규칙에서 만든다.** VLM은 배출 기준을 모르므로
            # 행동을 지시하게 두면 규칙과 어긋난 안내가 나간다.
            parts.append(_action_sentence(resolution.required_actions))

        if resolution.safety_note:
            parts.append(resolution.safety_note)

    message = " ".join(p for p in parts if p).strip()
    if not message:
        message = "다시 한 번 찍어줄래?"

    return Feedback(title=title, message=message, ttsText=_tts(f"{title} {message}"))


def simple(title: str, message: str) -> Feedback:
    """규칙·VLM을 거치지 않는 단순 안내(품질 미달, 얼굴 검출 등)."""
    return Feedback(title=title, message=message, ttsText=_tts(f"{title} {message}"))
