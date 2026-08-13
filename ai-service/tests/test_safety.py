"""STEP 3 — 안전 필터 테스트.

얼굴이 찍힌 사진을 저장소에 넣을 수는 없으므로(아동 개인정보 문제를 그대로
재현하게 된다) 여기서는 **검출기가 실제로 돌고, 얼굴이 없을 때 통과시키는지**를
확인한다. 양성 검출은 평가셋 촬영 때 실사진으로 확인한다.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.services import safety

pytestmark = pytest.mark.skipif(
    not get_settings().face_model_path.exists(),
    reason="BlazeFace 가중치 없음",
)


def noisy(width: int = 320, height: int = 240) -> Image.Image:
    rng = np.random.default_rng(seed=7)
    return Image.fromarray(
        rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8), mode="RGB"
    )


def test_model_file_is_bundled():
    """가중치를 저장소에 넣어 둔 이유 — 팀원이 따로 받지 않아도 되게 하려고."""
    path = get_settings().face_model_path
    assert path.exists()
    assert path.stat().st_size > 100_000


def test_blank_image_has_no_face():
    check = safety.detect_faces(Image.new("RGB", (256, 256), (200, 200, 200)))
    assert not check.has_face
    assert check.face_count == 0


def test_noise_is_not_a_face():
    assert not safety.detect_faces(noisy()).has_face


def test_grayscale_input_is_accepted():
    """전처리를 거치면 RGB지만, 다른 경로로 들어와도 터지지 않아야 한다."""
    gray = Image.new("L", (256, 256), 128)
    assert not safety.detect_faces(gray).has_face


def test_detector_is_reused_across_calls():
    """매 호출마다 tflite를 다시 읽으면 장당 수백 ms가 그냥 날아간다."""
    first = safety._load_detector()
    second = safety._load_detector()
    assert first is second


def test_threshold_sits_between_the_measured_distributions():
    """실측 회귀 — 임계값이 두 분포 사이에 있어야 한다.

    아래로 내려가면(< 0.622) 캔 뚜껑을 얼굴로 오인해 멀쩡한 사진이 반려된다.
    위로 올라가면(> 0.832) 화면을 채운 진짜 얼굴을 놓친다. 놓치면 아동 얼굴이
    그대로 외부 API로 넘어간다.

    측정 근거 (README '얼굴 검출 임계값' 절):
      물건 사진 62장 최대 오탐   0.622
      공개 인물 사진 근접/원본   0.832 ~ 0.983
    """
    threshold = get_settings().face_min_confidence
    highest_false_positive = 0.622
    lowest_true_positive = 0.832
    assert highest_false_positive < threshold < lowest_true_positive
