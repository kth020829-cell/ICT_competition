"""STEP 2 — 실제 가중치를 쓰는 검출 테스트.

가중치나 평가 사진이 없으면 통째로 건너뛴다. 팀원이 자산 없이 클론해도
테스트가 빨갛게 뜨지 않게 하려는 것이다.
"""

from __future__ import annotations

import csv

import pytest

from app.core.config import get_settings
from app.schemas.enums import YOLO_CLASS_ORDER, AnalysisStatus
from app.schemas.request import AnalyzeRequest
from app.schemas.response import AnalyzeResponse

settings = get_settings()
IMAGES_DIR = settings.rules_path.parents[2] / "eval_frozen" / "images"
CSV_PATH = IMAGES_DIR.parent / "eval_frozen_labels.csv"

pytestmark = pytest.mark.skipif(
    not settings.yolo_weights_path.exists(),
    reason="dasibom_v1_best.pt 없음 — app/models/weights/ 에 두면 실행된다",
)


def available_samples(limit: int = 6) -> list[tuple[str, str]]:
    if not CSV_PATH.exists() or not IMAGES_DIR.exists():
        return []
    samples = []
    # utf-8-sig — CSV는 Excel 호환을 위해 UTF-8 BOM으로 저장한다.
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fp:
        for row in csv.DictReader(fp):
            name = row["filename"].strip()
            if (IMAGES_DIR / name).exists() and row["yolo_class"].strip() != "(폴백)":
                samples.append((name, row["yolo_class"].strip()))
            if len(samples) >= limit:
                break
    return samples


SAMPLES = available_samples()
needs_photos = pytest.mark.skipif(not SAMPLES, reason="eval_frozen/images/ 에 사진이 없음")


def test_weights_class_order_matches_spec():
    """가중치의 클래스 순서가 어긋나면 이후 모든 라벨이 잘못된다. (지시서 §2.2)"""
    from app.services.detector import _load_model

    model = _load_model()
    names = model.names
    loaded = [names[i] for i in sorted(names)]
    assert loaded == list(YOLO_CLASS_ORDER)


@needs_photos
def test_detect_returns_normalized_boxes():
    from app.services import detector, preprocess

    name, _ = SAMPLES[0]
    prepared = preprocess.prepare((IMAGES_DIR / name).read_bytes())
    result = detector.detect(prepared.image)

    for candidate in result.candidates:
        box = candidate.box
        assert 0.0 <= box.x <= 1.0
        assert 0.0 <= box.y <= 1.0
        assert 0.0 < box.width <= 1.0
        assert 0.0 < box.height <= 1.0
        # 박스가 이미지 밖으로 넘치지 않아야 크롭이 안전하다.
        assert box.x + box.width <= 1.0001
        assert box.y + box.height <= 1.0001
        assert candidate.class_code in YOLO_CLASS_ORDER
        assert 0.0 <= candidate.confidence <= 1.0


@needs_photos
def test_candidates_sorted_by_confidence():
    from app.services import detector, preprocess

    name, _ = SAMPLES[0]
    prepared = preprocess.prepare((IMAGES_DIR / name).read_bytes())
    result = detector.detect(prepared.image)

    scores = [c.confidence for c in result.candidates]
    assert scores == sorted(scores, reverse=True)
    if result.best:
        assert result.best.confidence == scores[0]


@needs_photos
@pytest.mark.vlm
@pytest.mark.parametrize("name,expected", SAMPLES)
def test_pipeline_produces_valid_response(name, expected):
    """실제 사진으로 파이프라인을 끝까지 돌려 응답 계약을 확인한다.

    YOLO 클래스가 맞는지는 보지 않는다. 참고 지표이고 VLM이 교정한다. (§7.3-2)
    품목 판정이 맞는지도 여기서 보지 않는다. 그건 scripts/evaluate.py 의 일이다.
    여기서 보는 것은 **응답이 계약을 지키는가**뿐이다.
    """
    from app.services import pipeline

    req = AnalyzeRequest(scanSessionId="scan_test", phase="BEFORE")
    response = pipeline.run((IMAGES_DIR / name).read_bytes(), req)

    assert isinstance(response, AnalyzeResponse)
    assert response.scan_session_id == "scan_test"
    assert response.analysis_id.startswith("analysis_")
    assert response.processing.elapsed_ms >= 0

    if response.detection.bounding_box is not None:
        assert response.detection.class_code in YOLO_CLASS_ORDER

    if response.status in {AnalysisStatus.ACTION_REQUIRED, AnalysisStatus.COMPLETED}:
        # 판정이 끝났으면 품목명·배출 결론·states가 모두 있어야 한다.
        assert response.detection.item_name_ko
        assert response.disposal is not None
        assert response.disposal.rule_id
        assert response.states
        # Before의 정답은 준비 안내다. (지시서 §4.3)
        assert response.status != AnalysisStatus.IMPROVED
    else:
        # 거부·실패는 반드시 error를 동반한다.
        assert response.error is not None


# --------------------------------------------------------------------------
# MULTIPLE_OBJECTS 오탐 (실측 회귀)
# --------------------------------------------------------------------------
def test_overlap_ratio_measures_containment():
    from app.services.detector import Box

    big = Box(x=0.0, y=0.0, width=1.0, height=1.0)
    inside = Box(x=0.1, y=0.1, width=0.3, height=0.3)
    # 작은 박스가 큰 박스 안에 완전히 들어가면 1.0
    assert inside.overlap_ratio(big) == pytest.approx(1.0)
    assert big.overlap_ratio(inside) == pytest.approx(1.0)

    apart = Box(x=0.6, y=0.6, width=0.3, height=0.3)
    assert inside.overlap_ratio(apart) == 0.0


def test_stacked_slices_of_one_object_are_not_two_objects():
    """실측 회귀 — YOLO가 큰 종이를 가로 띠로 쪼갠다.

    라미네이팅 포스터 한 장이 전체 폭 × 세로 절반짜리 박스 세 개로 잡혔다.
    겹침을 보지 않으면 정상 사진이 MULTIPLE_OBJECTS로 반려된다.
    """
    from app.core.config import get_settings
    from app.services.detector import Box

    settings = get_settings()
    top = Box(x=0.01, y=0.06, width=0.99, height=0.44)
    bottom = Box(x=0.00, y=0.42, width=0.98, height=0.50)

    assert bottom.area >= top.area * settings.multiple_object_area_ratio
    # 인접 분할이므로 겹침이 임계값을 넘어 같은 물체로 판정되어야 한다.
    assert bottom.overlap_ratio(top) >= settings.multiple_object_overlap_ratio


def test_genuinely_separate_objects_still_count():
    from app.core.config import get_settings
    from app.services.detector import Box

    settings = get_settings()
    left = Box(x=0.02, y=0.2, width=0.4, height=0.6)
    right = Box(x=0.55, y=0.2, width=0.4, height=0.6)

    assert right.area >= left.area * settings.multiple_object_area_ratio
    assert right.overlap_ratio(left) < settings.multiple_object_overlap_ratio
