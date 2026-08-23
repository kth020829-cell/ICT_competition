"""VLM 상태 판정 — 지시서 §6 파이프라인 8단계, STEP 4.

크롭 이미지(또는 폴백 경로의 원본)를 Claude에 넘겨 **품목과 상태를 최종 판정**한다.
YOLO 클래스는 프롬프트를 고르는 힌트로만 쓰고, 결론은 여기서 나온다. (지시서 §11-3)

설계상 중요한 두 가지.

1. **구조화 출력(structured outputs)을 쓴다.** JSON을 프롬프트로 부탁하고 파싱에
   실패하면 재시도하는 구조는 지연과 실패율을 모두 키운다. 스키마를 API에 넘기면
   형식이 보장되므로 파싱 실패 경로 자체가 사라진다.
2. **판정과 아동 피드백을 한 번에 받는다.** 피드백 생성을 두 번째 호출로 분리하면
   비용과 지연이 두 배가 된다. 같은 응답에 `childMessage`를 함께 받는다.

프롬프트는 코드에 넣지 않고 `app/prompts/` 파일에서 읽는다. (지시서 §11-6)
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image

from app.core.config import get_settings
from app.schemas.enums import (
    ALL_STATE_KEYS,
    ITEM_TO_CLASS,
    STATE_SCHEMA,
    ErrorCode,
    StateValue,
)

logger = logging.getLogger(__name__)

#: 품목을 특정하지 못했을 때 VLM이 고르는 값.
UNKNOWN_ITEM = "알 수 없음"


@dataclass(frozen=True)
class StateJudgement:
    """VLM 판정 결과."""

    item_name_ko: str | None
    class_code: str | None
    is_waste: bool
    confidence: float
    #: 판정된 품목의 STATE_SCHEMA로 이미 걸러진 상태값.
    states: dict[str, tuple[StateValue, float]] = field(default_factory=dict)
    child_message: str = ""
    #: 실제로 응답을 만든 모델. 승급이 일어났는지 확인하는 용도.
    model_used: str = ""


class VlmError(RuntimeError):
    """VLM 호출 실패. `code` 로 실패 종류를 구분한다."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# 프롬프트 로딩
# --------------------------------------------------------------------------
@lru_cache(maxsize=16)
def _read_prompt(path_str: str) -> str:
    return Path(path_str).read_text(encoding="utf-8")


def _build_prompt(class_hint: str | None) -> str:
    """기본 지침 + 클래스별 추가 지침.

    클래스 힌트가 없으면(폴백 경로) `_fallback.txt` 를 붙인다. YOLO가 못 찾은
    품목이 그쪽으로 몰리므로, 그 목록을 알려주는 편이 판정에 유리하다.
    """
    settings = get_settings()
    base = _read_prompt(str(settings.prompts_dir / "state_analysis.txt"))

    name = f"{class_hint}.txt" if class_hint else "_fallback.txt"
    item_path = settings.prompts_dir / "items" / name
    if not item_path.exists():
        logger.warning("품목 프롬프트 없음: %s (기본 지침만 사용)", item_path)
        return base
    return f"{base}\n\n---\n\n{_read_prompt(str(item_path))}"


# --------------------------------------------------------------------------
# 출력 스키마
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _output_schema() -> dict:
    """구조화 출력 스키마.

    품목명을 enum으로 묶어 도감 밖의 값이 나오지 않게 한다. 자유 문자열을 받으면
    RAG 조회에서 키가 어긋나 그대로 실패한다.
    """
    state_object = {
        "type": "object",
        "properties": {
            "value": {"type": "string", "enum": [v.value for v in StateValue]},
            "confidence": {"type": "number"},
        },
        "required": ["value", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "itemNameKo": {
                "type": "string",
                "enum": [*ITEM_TO_CLASS.keys(), UNKNOWN_ITEM],
            },
            "isWaste": {"type": "boolean"},
            "confidence": {"type": "number"},
            "states": {
                "type": "object",
                "properties": dict.fromkeys(ALL_STATE_KEYS, state_object),
                "required": list(ALL_STATE_KEYS),
                "additionalProperties": False,
            },
            "childMessage": {"type": "string"},
        },
        "required": ["itemNameKo", "isWaste", "confidence", "states", "childMessage"],
        "additionalProperties": False,
    }


# --------------------------------------------------------------------------
# 이미지 인코딩
# --------------------------------------------------------------------------
def _encode(image: Image.Image) -> str:
    """크롭을 JPEG base64로 만든다.

    긴 변을 제한해 토큰 비용을 예측 가능하게 한다. 크롭은 원본보다 작지만
    상한이 없으면 근접 촬영에서 그대로 커진다.
    """
    settings = get_settings()
    img = image.convert("RGB")

    longest = max(img.size)
    if longest > settings.vlm_max_edge:
        scale = settings.vlm_max_edge / longest
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.LANCZOS,
        )

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=88)
    return base64.standard_b64encode(buffer.getvalue()).decode("ascii")


@lru_cache(maxsize=1)
def _client():
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise VlmError(ErrorCode.VLM_UNAVAILABLE, "ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    import anthropic  # noqa: PLC0415  — 무거우므로 필요할 때만

    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.vlm_timeout_seconds,
        max_retries=1,
    )


# --------------------------------------------------------------------------
# 판정
# --------------------------------------------------------------------------
def _call(model: str, prompt: str, image_b64: str) -> dict:
    import anthropic  # noqa: PLC0415

    settings = get_settings()
    try:
        response = _client().messages.create(
            model=model,
            max_tokens=settings.vlm_max_tokens,
            system=prompt,
            output_config={
                "format": {"type": "json_schema", "schema": _output_schema()},
                # 사고 깊이를 낮춰 지연을 줄인다. 아이가 기다리는 화면이다.
                "effort": settings.vlm_effort,
            },
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": "이 물건을 판정해줘."},
                    ],
                }
            ],
        )
    except anthropic.APITimeoutError as exc:
        raise VlmError(ErrorCode.AI_TIMEOUT, f"VLM 응답 시간 초과: {exc}") from exc
    except anthropic.RateLimitError as exc:
        raise VlmError(ErrorCode.VLM_UNAVAILABLE, f"요청 한도 초과: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise VlmError(ErrorCode.VLM_UNAVAILABLE, f"VLM 오류 {exc.status_code}") from exc
    except anthropic.APIConnectionError as exc:
        raise VlmError(ErrorCode.VLM_UNAVAILABLE, f"VLM 연결 실패: {exc}") from exc

    # 안전 분류기가 요청을 거절한 경우. content가 비어 있어 그냥 읽으면 터진다.
    if response.stop_reason == "refusal":
        raise VlmError(ErrorCode.INVALID_AI_OUTPUT, "VLM이 요청을 거절했습니다.")

    # 출력 한도에서 잘린 경우. JSON이 중간에서 끊겨 파싱이 실패하는데, 그대로 두면
    # '알 수 없는 파싱 오류'로 보여 원인을 찾기 어렵다. 여기서 이름을 붙여 준다.
    if response.stop_reason == "max_tokens":
        raise VlmError(
            ErrorCode.INVALID_AI_OUTPUT,
            f"VLM 응답이 max_tokens({settings.vlm_max_tokens})에서 잘렸습니다. "
            "VLM_MAX_TOKENS를 올리세요.",
        )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise VlmError(
            ErrorCode.INVALID_AI_OUTPUT,
            f"VLM 응답이 비어 있습니다 (stop_reason={response.stop_reason}).",
        )

    import json  # noqa: PLC0415

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        # 스키마를 강제했으므로 여기 오면 안 된다. 오면 계약이 깨진 것이다.
        raise VlmError(ErrorCode.INVALID_AI_OUTPUT, f"JSON 파싱 실패: {exc}") from exc

    payload["_model"] = response.model
    return payload


def _to_judgement(payload: dict) -> StateJudgement:
    item = payload.get("itemNameKo")
    if item == UNKNOWN_ITEM:
        item = None

    class_code = ITEM_TO_CLASS.get(item) if item else None

    # 품목이 정해졌으면 그 품목의 스키마 키만 남긴다. 나머지는 애초에 물어본 적
    # 없는 상태이므로 응답에 실어 보내지 않는다.
    allowed = set(STATE_SCHEMA.get(class_code, [])) if class_code else set()
    states: dict[str, tuple[StateValue, float]] = {}
    for key, raw in (payload.get("states") or {}).items():
        if allowed and key not in allowed:
            continue
        try:
            value = StateValue(raw["value"])
        except (KeyError, ValueError):
            value = StateValue.UNKNOWN
        states[key] = (value, float(raw.get("confidence", 0.0)))

    # 스키마 키인데 응답에 빠진 것은 unknown으로 채운다. 키를 빼버리면
    # '해당 없음'과 '판정 실패'를 구분할 수 없다. (지시서 §5.3)
    for key in allowed:
        states.setdefault(key, (StateValue.UNKNOWN, 0.0))

    return StateJudgement(
        item_name_ko=item,
        class_code=class_code,
        is_waste=bool(payload.get("isWaste", True)),
        confidence=float(payload.get("confidence", 0.0)),
        states=states,
        child_message=str(payload.get("childMessage", "")).strip(),
        model_used=str(payload.get("_model", "")),
    )


def analyze(image: Image.Image, *, class_hint: str | None = None) -> StateJudgement:
    """이미지 한 장의 품목과 상태를 판정한다.

    Haiku로 먼저 시도하고, 실패하면 Sonnet으로 한 번 승급한다. (지시서 §2.3)
    승급은 재시도가 아니라 모델 교체다. 같은 모델로 다시 던져 봐야
    같은 이유로 실패한다.
    """
    settings = get_settings()
    prompt = _build_prompt(class_hint)
    image_b64 = _encode(image)

    try:
        return _to_judgement(_call(settings.vlm_primary_model, prompt, image_b64))
    except VlmError as exc:
        if not settings.vlm_escalate_on_failure:
            raise
        logger.warning(
            "%s 실패(%s) → %s 로 승급",
            settings.vlm_primary_model,
            exc.code,
            settings.vlm_fallback_model,
        )
        return _to_judgement(_call(settings.vlm_fallback_model, prompt, image_b64))
