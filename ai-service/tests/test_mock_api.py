"""STEP 1 Mock 서버 계약 테스트.

값이 가짜여도 **스키마와 코드값은 진짜와 같아야** 백엔드 연동이 의미가 있다.
그래서 여기서는 응답의 모양과 코드값 유효성을 검사한다.
"""

import base64
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mocks.scenarios import SCENARIOS
from app.schemas.enums import (
    ACTION_LABEL_KO,
    STATE_SCHEMA,
    ActionCode,
    AnalysisStatus,
    DisposalCategory,
    ErrorCode,
    StateValue,
)

client = TestClient(app)

#: 1x1 투명 PNG. mock 모드는 픽셀을 보지 않으므로 최소 바이트면 충분하다.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def post_analyze(scenario: str | None = None, **fields) -> dict:
    data = {"scanSessionId": "scan_test_0001", "phase": "BEFORE", **fields}
    if scenario:
        data["mockScenario"] = scenario
    response = client.post(
        "/v1/analyze",
        data=data,
        files={"image": ("test.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# 기동 확인
# --------------------------------------------------------------------------
def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["aiMode"] == "mock"
    # STEP 진행 여부를 판단하는 자산 체크가 노출돼야 한다.
    assert set(body["checks"]) >= {"yoloWeights", "anthropicApiKey", "recyclingRules"}


def test_scenario_catalog_is_complete():
    """지시서 STEP 1이 요구한 9개 시나리오가 모두 있어야 한다."""
    required = {
        "pet_action_required",
        "pet_completed",
        "after_success",
        "after_partial",
        "face_detected",
        "not_waste",
        "multiple_objects",
        "low_confidence",
        "ai_timeout",
    }
    assert required <= set(SCENARIOS)
    assert required <= set(client.get("/v1/mock/scenarios").json()["scenarios"])


# --------------------------------------------------------------------------
# 응답 계약
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_every_scenario_satisfies_contract(scenario):
    body = post_analyze(scenario)

    # 필수 최상위 키 (지시서 §5.5)
    for key in ("analysisId", "scanSessionId", "phase", "status", "safety",
                "detection", "feedback", "processing"):
        assert key in body, f"{scenario}: {key} 누락"

    assert body["scanSessionId"] == "scan_test_0001"
    assert body["status"] in {s.value for s in AnalysisStatus}
    assert body["analysisId"].startswith("analysis_")

    # 자유 문자열만 주지 않는다. 행동에는 반드시 코드가 붙는다. (지시서 §5.2)
    for action in body["requiredActions"]:
        assert action["code"] in {a.value for a in ActionCode}
        assert action["labelKo"] == ACTION_LABEL_KO[ActionCode(action["code"])]

    for key, state in body["states"].items():
        assert state["value"] in {v.value for v in StateValue}
        assert 0.0 <= state["confidence"] <= 1.0

    if body["disposal"]:
        assert body["disposal"]["categoryCode"] in {d.value for d in DisposalCategory}

    if body["error"]:
        assert body["error"]["code"] in {e.value for e in ErrorCode}

    # TTS 텍스트는 항상 채워져야 한다. 읽어줄 문장이 없으면 화면이 빈다.
    assert body["feedback"]["ttsText"].strip()

    proc = body["processing"]
    assert proc["modelVersion"] and proc["promptVersion"] and proc["ruleVersion"]


@pytest.mark.parametrize("scenario", ["pet_action_required", "pet_completed", "after_partial"])
def test_states_follow_item_schema(scenario):
    """품목 스키마의 키를 전부 채운다. 빠뜨리면 '해당 없음'과 '판정 실패'가 섞인다."""
    body = post_analyze(scenario)
    class_code = body["detection"]["classCode"]
    assert set(body["states"]) == set(STATE_SCHEMA[class_code])


def test_before_does_not_conclude_disposal():
    """지시서 §4.3 — Before의 정답은 배출 결론이 아니라 '준비 필요 안내'다."""
    body = post_analyze("pet_action_required")
    assert body["status"] == AnalysisStatus.ACTION_REQUIRED
    assert body["requiredActions"], "Before인데 안내할 행동이 없다"
    assert body.get("rewardEligible") is not True


def test_pet_keeps_cap_on():
    """지시서 §4.4 — 투명 페트병은 뚜껑을 닫아서 배출한다. REMOVE_CAP을 요구하면 오답."""
    for scenario in ("pet_action_required", "pet_completed", "after_partial"):
        body = post_analyze(scenario)
        codes = [a["code"] for a in body["requiredActions"]]
        assert ActionCode.REMOVE_CAP not in codes, f"{scenario}: 페트병에 뚜껑 분리를 요구했다"


def test_after_returns_comparison():
    """지시서 §5.6 — AFTER에는 비교 블록이 실린다."""
    body = post_analyze("after_partial", phase="AFTER", beforeAnalysisId="analysis_prev")
    assert body["phase"] == "AFTER"
    comparison = body["comparison"]
    assert comparison["sameClass"] is True
    assert ActionCode.REMOVE_LABEL in comparison["improvedActions"]
    assert ActionCode.CRUSH in comparison["remainingActions"]
    # 보상은 백엔드가 결정한다. AI는 참고값만 준다.
    assert body["rewardEligible"] is False


def test_after_success_clears_remaining_actions():
    body = post_analyze("after_success", phase="AFTER", beforeAnalysisId="analysis_prev")
    assert body["status"] == AnalysisStatus.IMPROVED
    assert body["comparison"]["remainingActions"] == []
    assert body["requiredActions"] == []


# --------------------------------------------------------------------------
# 거부·실패 경로
# --------------------------------------------------------------------------
def test_face_detected_is_rejected_not_5xx():
    """안전 필터도 200 + 구조화된 본문으로 온다. 백엔드가 한 경로로 파싱하게."""
    body = post_analyze("face_detected")
    assert body["status"] == AnalysisStatus.REJECTED
    assert body["safety"]["faceDetected"] is True
    assert body["error"]["code"] == ErrorCode.FACE_DETECTED
    assert body["error"]["retryable"] is True
    assert body["disposal"] is None


def test_not_waste_flags_safety():
    body = post_analyze("not_waste")
    assert body["safety"]["isWasteImage"] is False
    assert body["error"]["code"] == ErrorCode.NOT_WASTE


def test_timeout_is_failed_not_rejected():
    """서버 문제는 아이 잘못이 아니다. REJECTED와 구분한다."""
    body = post_analyze("ai_timeout")
    assert body["status"] == AnalysisStatus.FAILED
    assert body["error"]["code"] == ErrorCode.AI_TIMEOUT


# --------------------------------------------------------------------------
# 입력 검증
# --------------------------------------------------------------------------
def test_phase_default_selects_before_scenario():
    body = post_analyze()
    assert body["phase"] == "BEFORE"
    assert body["status"] == AnalysisStatus.ACTION_REQUIRED


def test_header_can_select_scenario():
    response = client.post(
        "/v1/analyze",
        data={"scanSessionId": "scan_test_0002", "phase": "BEFORE"},
        files={"image": ("t.png", io.BytesIO(TINY_PNG), "image/png")},
        headers={"X-Mock-Scenario": "not_waste"},
    )
    assert response.json()["error"]["code"] == ErrorCode.NOT_WASTE


def test_unknown_scenario_is_rejected():
    """오타를 조용히 넘기면 백엔드가 잘못된 시나리오로 개발하게 된다."""
    response = client.post(
        "/v1/analyze",
        data={"scanSessionId": "s", "phase": "BEFORE", "mockScenario": "typo_here"},
        files={"image": ("t.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 400


def test_missing_image_is_422():
    response = client.post("/v1/analyze", data={"scanSessionId": "s", "phase": "BEFORE"})
    assert response.status_code == 422


def test_missing_session_id_is_422():
    response = client.post(
        "/v1/analyze",
        data={"phase": "BEFORE"},
        files={"image": ("t.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 422


def test_empty_image_is_400():
    response = client.post(
        "/v1/analyze",
        data={"scanSessionId": "s", "phase": "BEFORE"},
        files={"image": ("t.png", io.BytesIO(b""), "image/png")},
    )
    assert response.status_code == 400


def test_unsupported_content_type_is_415():
    response = client.post(
        "/v1/analyze",
        data={"scanSessionId": "s", "phase": "BEFORE"},
        files={"image": ("t.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert response.status_code == 415


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------
def test_compare_endpoint():
    response = client.post(
        "/v1/compare",
        json={"beforeAnalysisId": "analysis_a", "afterAnalysisId": "analysis_b"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["comparison"]["sameClass"] is True
    assert body["rewardEligible"] is False


# --------------------------------------------------------------------------
# 코드값 정합성 (지시서 §5.2)
# --------------------------------------------------------------------------
def test_action_labels_cover_every_code():
    assert set(ACTION_LABEL_KO) == set(ActionCode)


def test_state_schema_has_no_unknown_keys():
    known = {
        "labelAttached", "capAttached", "contentRemaining", "flattened",
        "contaminated", "rinsed", "unfolded", "tapeAttached", "coated",
    }
    for class_code, keys in STATE_SCHEMA.items():
        assert set(keys) <= known, f"{class_code}에 정의되지 않은 상태 키가 있다"
