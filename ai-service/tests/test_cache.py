"""STEP 9 — 이미지 해시 캐시 테스트.

VLM을 부르지 않고 저장·조회 규칙만 검사한다. 캐시 디렉터리는 tmp_path로
갈아끼워 실제 `app/cache/` 를 건드리지 않는다.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.schemas.enums import (
    ActionCode,
    AnalysisStatus,
    DetectionSource,
    DisposalCategory,
    ErrorCode,
)
from app.schemas.request import AnalyzeRequest
from app.schemas.response import (
    AnalysisError,
    AnalyzeResponse,
    Detection,
    Disposal,
    Feedback,
    Processing,
    RequiredAction,
    Safety,
    StateItem,
)
from app.services import cache


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_response(*, error: ErrorCode | None = None) -> AnalyzeResponse:
    settings = get_settings()
    return AnalyzeResponse(
        analysisId="analysis_original",
        scanSessionId="scan_original",
        phase="BEFORE",
        status=AnalysisStatus.FAILED if error else AnalysisStatus.ACTION_REQUIRED,
        safety=Safety(faceDetected=False, isWasteImage=True),
        detection=Detection(
            classCode="pet",
            classNameKo="페트병",
            itemNameKo="투명 페트병",
            confidence=0.9,
            source=DetectionSource.YOLO,
        ),
        states={"labelAttached": StateItem(value="yes", confidence=0.9)},
        requiredActions=[RequiredAction(code=ActionCode.REMOVE_LABEL, labelKo="라벨 떼기")],
        disposal=Disposal(
            categoryCode=DisposalCategory.CLEAR_PET_BIN,
            categoryNameKo="투명 페트병 전용함",
            ruleId="CJ-PET-001",
        ),
        feedback=Feedback(title="찾았어", message="라벨을 떼줄래?", ttsText="찾았어 라벨을 떼줄래?"),
        error=(
            AnalysisError(code=error, messageKo="실패", retryable=True) if error else None
        ),
        processing=Processing(
            modelVersion=settings.model_version,
            promptVersion=settings.prompt_version,
            ruleVersion=settings.rule_version,
        ),
    )


def request(**kwargs) -> AnalyzeRequest:
    fields = {"scanSessionId": "scan_1", "phase": "BEFORE", **kwargs}
    return AnalyzeRequest(**fields)


def test_round_trip():
    payload, req = b"fake-image-bytes", request()
    assert cache.get(payload, req) is None

    cache.put(payload, req, make_response())
    hit = cache.get(payload, req)
    assert hit is not None
    assert hit.detection.item_name_ko == "투명 페트병"
    assert hit.required_actions[0].code == ActionCode.REMOVE_LABEL
    assert hit.disposal.rule_id == "CJ-PET-001"


def test_different_image_is_a_miss():
    req = request()
    cache.put(b"image-a", req, make_response())
    assert cache.get(b"image-b", req) is None


@pytest.mark.parametrize(
    "changed",
    [
        {"phase": "AFTER"},
        {"regionCode": "KR-11-SEOUL"},
        {"userChoice": "water"},
    ],
)
def test_request_conditions_are_part_of_the_key(changed):
    """같은 사진이라도 조건이 다르면 결과가 다르다.

    아이스팩은 userChoice에 따라 결론이 갈리고, phase에 따라 비교 결과가 달라진다.
    조건을 키에 넣지 않으면 첫 결과가 다른 조건에도 그대로 되돌아간다.
    """
    payload = b"same-image"
    cache.put(payload, request(), make_response())
    assert cache.get(payload, request(**changed)) is None


def test_failures_are_not_cached():
    """흔들린 사진이나 일시적 타임아웃을 박아두면 다시 찍어도 같은 실패가 온다."""
    payload, req = b"blurry", request()
    cache.put(payload, req, make_response(error=ErrorCode.IMAGE_TOO_BLURRY))
    assert cache.get(payload, req) is None


def test_corrupt_entry_is_discarded_not_raised():
    """캐시가 깨졌다고 서비스가 멈추면 안 된다."""
    payload, req = b"image", request()
    cache.put(payload, req, make_response())
    path = cache._path(cache._key(payload, req))
    path.write_text("{ 깨진 JSON", encoding="utf-8")

    assert cache.get(payload, req) is None
    assert not path.exists()


def test_stats_and_clear():
    cache.put(b"a", request(), make_response())
    cache.put(b"b", request(), make_response())
    assert cache.stats()["entries"] == 2
    assert cache.clear() == 2
    assert cache.stats()["entries"] == 0


def test_cache_stores_no_pixels():
    """이미지는 저장하지 않는다는 것이 이 캐시의 계약이다. (지시서 §11-5)"""
    payload = b"\x89PNG\r\n\x1a\n" + b"secret-pixels" * 50
    req = request()
    cache.put(payload, req, make_response())

    path = cache._path(cache._key(payload, req))
    stored = path.read_bytes()
    assert b"secret-pixels" not in stored
    # 파일 이름도 해시라 원본 바이트가 드러나지 않는다.
    assert b"PNG" not in stored
