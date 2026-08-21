"""백엔드 세션 result 양식 변환 테스트 (명세서 §3).

가장 중요한 계약은 "백엔드가 `SessionResultRequest(**응답)` 으로 그대로 받을 수
있다"는 것이다. 그래서 필드 이름과 타입을 그 모델 그대로 재현해 검증한다.
"""

from __future__ import annotations

import io
import logging

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import BaseModel

from app.main import app
from app.mocks import scenarios
from app.schemas.enums import (
    ITEM_TO_CARD_TYPE,
    ITEM_TO_CLASS,
    AnalysisStatus,
    Phase,
)
from app.schemas.request import AnalyzeRequest
from app.schemas.response import Detection
from app.services import backend_adapter


# 백엔드 app/routers/session.py 의 SessionResultRequest 를 그대로 옮겨온 것.
# 백엔드 코드를 임포트할 수 없으므로 계약을 여기에 복제해 지킨다. 백엔드가
# 이 모양을 바꾸면 이 테스트가 먼저 깨져야 한다.
class SessionResultRequest(BaseModel):
    detectedClass: str
    confidence: float
    needsAction: bool
    actions: list[str]
    disposalCategory: str
    feedbackText: str


@pytest.fixture
def client():
    return TestClient(app)


def image_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (120, 140, 160)).save(buf, format="JPEG")
    return buf.getvalue()


def post(client: TestClient, **fields):
    data = {"scanSessionId": "scan_test", "phase": "BEFORE", **fields}
    return client.post(
        "/v1/analyze/session",
        data=data,
        files={"image": ("t.jpg", image_bytes(), "image/jpeg")},
    )


# --------------------------------------------------------------------------
# 백엔드 모델과의 계약
# --------------------------------------------------------------------------
def test_response_fits_backend_session_result_request(client):
    """응답을 백엔드 모델에 그대로 넣을 수 있어야 한다."""
    body = post(client).json()

    parsed = SessionResultRequest(**body)  # 부가 필드는 pydantic이 무시한다

    # detectedClass 는 클래스(pet)가 아니라 Firestore card 의 type 이다.
    # 백엔드 collect_card() 가 `type == detectedClass` 로 카드를 찾는다.
    assert parsed.detectedClass == "transparency_plastic_bottle"
    assert body["classCode"] == "pet"
    assert parsed.needsAction is True
    assert parsed.actions == ["라벨 떼기", "납작하게 누르기"]
    assert parsed.disposalCategory == "CLEAR_PET_BIN"
    assert parsed.feedbackText


def test_action_codes_ride_alongside_korean_labels(client):
    """미션·뱃지 판정용 코드가 한글 라벨과 같은 순서로 실려야 한다."""
    body = post(client).json()

    assert body["actionCodes"] == ["REMOVE_LABEL", "CRUSH"]
    assert len(body["actionCodes"]) == len(body["actions"])


def test_analysis_id_is_present_for_after_comparison(client):
    """analysisId 가 없으면 백엔드가 After 비교를 걸 수 없다."""
    body = post(client).json()

    assert body["analysisId"]
    assert body["aiStatus"] == "ACTION_REQUIRED"


def test_completed_item_needs_no_action(client):
    body = post(client, mockScenario="pet_completed").json()

    assert body["needsAction"] is False
    assert body["actions"] == []
    assert body["actionCodes"] == []
    # 백엔드는 needsAction 만 보고 COMPLETED 로 넘긴다.
    assert SessionResultRequest(**body).needsAction is False


# --------------------------------------------------------------------------
# AFTER — 남은 행동만 내보낸다
# --------------------------------------------------------------------------
def test_after_reports_only_remaining_actions(client):
    """Before에서 요구한 행동을 그대로 다시 내면 아이가 해낸 일이 지워진다."""
    body = post(
        client, phase="AFTER", mockScenario="after_partial", beforeAnalysisId="analysis_x"
    ).json()

    assert body["aiStatus"] == "PARTIALLY_IMPROVED"
    assert body["improved"] is False
    assert body["actionCodes"] == ["CRUSH"]
    assert body["actions"] == ["납작하게 누르기"]
    assert body["remainingActions"] == ["납작하게 누르기"]
    assert body["needsAction"] is True


def test_after_success_marks_improved(client):
    body = post(
        client, phase="AFTER", mockScenario="after_success", beforeAnalysisId="analysis_x"
    ).json()

    assert body["aiStatus"] == "IMPROVED"
    assert body["improved"] is True
    assert body["needsAction"] is False
    assert body["remainingActions"] == []


# --------------------------------------------------------------------------
# 거부·실패 — 품목이 없는 경우
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "scenario,code",
    [
        ("face_detected", "FACE_DETECTED"),
        ("not_waste", "NOT_WASTE"),
        ("multiple_objects", "MULTIPLE_OBJECTS"),
    ],
)
def test_rejected_still_fits_backend_model(client, scenario, code):
    """거부돼도 백엔드 필수 문자열 필드가 비어 있으면 안 된다(None 금지)."""
    body = post(client, mockScenario=scenario).json()

    parsed = SessionResultRequest(**body)  # None 이면 여기서 터진다
    assert parsed.detectedClass == ""
    assert parsed.disposalCategory == ""
    assert parsed.confidence == 0.0

    # 재촬영을 유도해야 하므로 needsAction 은 True 여야 한다. 백엔드가
    # `if needsAction: ACTION_REQUIRED` 로 상태를 정한다.
    assert parsed.needsAction is True

    assert body["error"]["code"] == code
    assert body["feedbackText"] == body["error"]["messageKo"]
    assert body["aiStatus"] == "REJECTED"


def test_rejected_feedback_is_child_readable(client):
    """오류 코드가 아니라 아이가 읽을 문장이 feedbackText 에 와야 한다."""
    body = post(client, mockScenario="face_detected").json()

    assert "FACE_DETECTED" not in body["feedbackText"]
    assert len(body["feedbackText"]) > 5


# --------------------------------------------------------------------------
# 입력 검증은 /v1/analyze 와 같아야 한다
# --------------------------------------------------------------------------
def test_same_input_validation_as_analyze(client):
    """두 경로의 통과 기준이 갈리면 백엔드가 어느 쪽을 쓰냐에 따라 달라진다."""
    for path in ("/v1/analyze", "/v1/analyze/session"):
        r = client.post(
            path,
            data={"scanSessionId": "s", "phase": "BEFORE"},
            files={"image": ("t.jpg", b"", "image/jpeg")},
        )
        assert r.status_code == 400, path

        r = client.post(
            path,
            data={"scanSessionId": "s", "phase": "BEFORE"},
            files={"image": ("t.gif", image_bytes(), "image/gif")},
        )
        assert r.status_code == 415, path


def test_unknown_mock_scenario_is_rejected(client):
    r = post(client, mockScenario="does_not_exist")
    assert r.status_code == 400


# --------------------------------------------------------------------------
# 단위 — 모든 mock 시나리오가 변환을 통과하는가
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(scenarios.SCENARIOS))
def test_every_scenario_converts(name):
    """어떤 시나리오든 백엔드 모델에 들어가야 한다."""
    handler = scenarios.SCENARIOS[name]
    phase = Phase.AFTER if name.startswith("after_") else Phase.BEFORE
    req = AnalyzeRequest(
        scanSessionId="scan_test", phase=phase, beforeAnalysisId="analysis_x"
    )

    result = backend_adapter.to_session_result(handler(req))

    body = result.model_dump(by_alias=True)
    parsed = SessionResultRequest(**body)

    assert isinstance(parsed.detectedClass, str)
    assert isinstance(parsed.disposalCategory, str)
    assert 0.0 <= parsed.confidence <= 1.0
    assert len(result.actions) == len(result.action_codes)
    assert result.ai_status in set(AnalysisStatus)


# --------------------------------------------------------------------------
# 도감 카드 매핑 — 백엔드 collect_card() 가 `type == detectedClass` 로 찾는다
# --------------------------------------------------------------------------
def test_every_encyclopedia_item_maps_to_a_card_type():
    """VLM이 낼 수 있는 품목은 전부 카드 type 이 있어야 한다.

    빠지면 그 품목만 도감에 조용히 등록되지 않는다. 판정은 정상으로 보여서
    발견이 늦다.
    """
    missing = [item for item in ITEM_TO_CLASS if item not in ITEM_TO_CARD_TYPE]
    assert missing == [], f"카드 type 이 없는 품목: {missing}"


def test_card_types_are_unique_except_merged_paper():
    """도감이 신문지·공책을 한 장으로 묶은 것 말고는 1:1이어야 한다."""
    seen: dict[str, list[str]] = {}
    for item, card in ITEM_TO_CARD_TYPE.items():
        seen.setdefault(card, []).append(item)

    shared = {c: items for c, items in seen.items() if len(items) > 1}
    assert shared == {"newspaper&notebook": ["신문지", "공책"]}, shared


def test_card_type_falls_back_to_class_when_item_unknown(caplog):
    """도감에 없는 품목이 오면 클래스로 떨어지되 조용하지 않아야 한다."""
    detection = Detection(
        classCode="pet", classNameKo="페트병", itemNameKo="존재하지 않는 물건",
        confidence=0.5,
    )
    with caplog.at_level(logging.WARNING):
        assert backend_adapter.card_type_for(detection) == "pet"
    assert "매핑에 없는 품목" in caplog.text


def test_card_type_uses_item_not_class(client):
    """같은 pet 클래스라도 품목이 다르면 카드가 달라야 한다."""
    a = post(client, mockScenario="pet_action_required").json()
    assert a["detectedClass"] == "transparency_plastic_bottle"
    assert a["classCode"] == "pet"


def test_rejected_has_no_card_type(client):
    """거부된 판정으로 카드를 주면 안 된다."""
    body = post(client, mockScenario="face_detected").json()
    assert body["detectedClass"] == ""
