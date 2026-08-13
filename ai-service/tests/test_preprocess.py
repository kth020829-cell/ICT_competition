"""STEP 2 — 전처리·크롭 단위 테스트.

가중치 없이 도는 것만 여기에 둔다. 검출은 test_detector.py.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.schemas.enums import ErrorCode
from app.services import cropper, preprocess
from app.services.detector import Box
from app.services.preprocess import ImageDecodeError


def to_bytes(image: Image.Image, fmt: str = "JPEG", **kwargs) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def noisy_image(width: int, height: int, brightness: int = 128) -> Image.Image:
    """고주파 잡음이 있는 이미지. 블러 검사를 통과할 만큼 경계가 많다."""
    rng = np.random.default_rng(seed=42)
    noise = rng.integers(0, 90, size=(height, width, 3), dtype=np.uint8)
    base = np.clip(noise.astype(np.int16) + brightness - 45, 0, 255).astype(np.uint8)
    return Image.fromarray(base, mode="RGB")


# --------------------------------------------------------------------------
# 디코딩
# --------------------------------------------------------------------------
def test_rejects_non_image_bytes():
    with pytest.raises(ImageDecodeError):
        preprocess.prepare(b"this is not an image")


def test_accepts_png_and_jpeg():
    for fmt in ("PNG", "JPEG"):
        prepared = preprocess.prepare(to_bytes(noisy_image(300, 200), fmt))
        assert prepared.image.mode == "RGB"


# --------------------------------------------------------------------------
# EXIF 회전 보정 (지시서 §11-4)
# --------------------------------------------------------------------------
def test_exif_orientation_is_applied():
    """Orientation=6은 시계방향 90도 회전이 필요하다는 뜻.

    보정하지 않으면 세로로 찍은 사진이 눕는다. 지시서가 별도 항목으로
    강조한 이유가 이것이다.
    """
    portrait = noisy_image(100, 300)  # 세로로 긴 원본

    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation
    payload = to_bytes(portrait, "JPEG", exif=exif)

    prepared = preprocess.prepare(payload)
    # 보정이 적용되면 가로/세로가 뒤바뀐다.
    assert (prepared.width, prepared.height) == (300, 100)


def test_no_exif_image_passes_through():
    prepared = preprocess.prepare(to_bytes(noisy_image(240, 160)))
    assert (prepared.width, prepared.height) == (240, 160)


# --------------------------------------------------------------------------
# 메타데이터 제거 (지시서 §11 개인정보)
# --------------------------------------------------------------------------
def test_gps_metadata_is_removed():
    """아동 위치정보가 남으면 안 된다."""
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (36.0, 38.0, 0.0)}  # GPSInfo
    exif[0x010F] = "TestCamera"  # Make
    payload = to_bytes(noisy_image(200, 200), "JPEG", exif=exif)

    prepared = preprocess.prepare(payload)

    assert not prepared.image.getexif()
    assert "exif" not in prepared.image.info


# --------------------------------------------------------------------------
# 클라이언트 규격 리사이즈 (지시서 §10)
# --------------------------------------------------------------------------
def test_large_image_is_resized_to_client_spec():
    settings = get_settings()
    prepared = preprocess.prepare(to_bytes(noisy_image(3000, 2000)))
    assert max(prepared.width, prepared.height) == settings.client_max_edge
    assert prepared.resized is True
    # 종횡비가 유지돼야 bounding box 좌표가 어긋나지 않는다.
    assert prepared.width / prepared.height == pytest.approx(3000 / 2000, rel=0.01)


def test_small_image_is_left_alone():
    prepared = preprocess.prepare(to_bytes(noisy_image(400, 300)))
    assert (prepared.width, prepared.height) == (400, 300)
    assert prepared.resized is False


# --------------------------------------------------------------------------
# 품질 검사
# --------------------------------------------------------------------------
def test_dark_image_is_flagged():
    dark = Image.new("RGB", (300, 300), (5, 5, 5))
    prepared = preprocess.prepare(to_bytes(dark))
    assert prepared.quality.error_code == ErrorCode.IMAGE_TOO_DARK
    assert not prepared.quality.ok


def test_flat_image_is_flagged_as_blurry():
    """경계가 전혀 없는 이미지는 라플라시안 분산이 0에 가깝다."""
    flat = Image.new("RGB", (300, 300), (128, 128, 128))
    prepared = preprocess.prepare(to_bytes(flat))
    assert prepared.quality.error_code == ErrorCode.IMAGE_TOO_BLURRY


def test_normal_image_passes():
    prepared = preprocess.prepare(to_bytes(noisy_image(400, 400)))
    assert prepared.quality.ok
    assert prepared.quality.error_code is None


def test_dark_beats_blurry_when_both_fail():
    """어두우면서 흐린 사진에는 '어두워'라고 말해야 행동이 교정된다."""
    dark_flat = Image.new("RGB", (300, 300), (3, 3, 3))
    prepared = preprocess.prepare(to_bytes(dark_flat))
    assert prepared.quality.error_code == ErrorCode.IMAGE_TOO_DARK


# --------------------------------------------------------------------------
# 크롭 (지시서 §11-5)
# --------------------------------------------------------------------------
def test_crop_applies_padding():
    image = noisy_image(1000, 1000)
    box = Box(x=0.4, y=0.4, width=0.2, height=0.2)  # 중앙 200x200

    cropped = cropper.crop(image, box, padding=0.0)
    assert cropped.size == (200, 200)

    padded = cropper.crop(image, box, padding=0.25)
    # 양쪽으로 25%씩 = 200 + 50 + 50
    assert padded.size == (300, 300)


def test_crop_clamps_to_image_bounds():
    """물체가 가장자리에 붙어 있어도 여백 때문에 이미지 밖으로 나가면 안 된다."""
    image = noisy_image(500, 500)
    box = Box(x=0.0, y=0.0, width=0.2, height=0.2)
    cropped = cropper.crop(image, box, padding=0.5)
    assert cropped.width <= 500 and cropped.height <= 500


def test_degenerate_box_falls_back_to_full_image():
    image = noisy_image(400, 400)
    box = Box(x=0.5, y=0.5, width=0.0, height=0.0)
    cropped = cropper.crop(image, box, padding=0.0)
    assert cropped.size == (400, 400)


def test_crop_and_discard_returns_independent_copy():
    """원본을 닫아도 크롭본은 살아 있어야 한다. 원본 폐기의 전제 조건이다."""
    image = noisy_image(600, 600)
    box = Box(x=0.25, y=0.25, width=0.5, height=0.5)

    cropped = cropper.crop_and_discard(image, box)

    # 원본이 닫힌 뒤에도 픽셀 접근이 가능해야 한다.
    assert cropped.getpixel((0, 0)) is not None
    assert cropped.width > 0
