"""전처리 — 지시서 §6 파이프라인 2~4단계.

    2. EXIF 회전 보정 (exif_transpose)   ← 누락하면 세로 사진이 눕는다
    3. EXIF GPS 등 메타데이터 제거        ← 아동 개인정보
    4. 품질 검사 (블러 스코어, 밝기)      → 미달 시 재촬영 유도

순서가 중요하다. 회전 보정은 EXIF를 읽어야 하므로 메타데이터 제거보다 **먼저** 한다.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.schemas.enums import ErrorCode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityReport:
    """품질 검사 결과. 미달이면 `error_code` 가 채워진다."""

    blur_score: float
    brightness: float
    error_code: ErrorCode | None = None

    @property
    def ok(self) -> bool:
        return self.error_code is None


@dataclass(frozen=True)
class PreparedImage:
    """전처리를 마친 이미지. 여기서부터 EXIF는 존재하지 않는다."""

    image: Image.Image
    width: int
    height: int
    quality: QualityReport
    #: 클라이언트 리사이즈 규격에 맞추느라 축소했는지 여부.
    resized: bool


class ImageDecodeError(ValueError):
    """이미지로 읽을 수 없는 바이트."""


def _strip_metadata(image: Image.Image) -> Image.Image:
    """픽셀만 남기고 EXIF·GPS·주석을 전부 버린다.

    `img.info` 를 지우는 것으로는 부족하다. 원시 픽셀 바이트로 새 이미지를 만들어야
    포맷별 부가 청크까지 확실히 떨어진다.
    """
    return Image.frombytes(image.mode, image.size, image.tobytes())


def _resize_to_client_spec(image: Image.Image, max_edge: int) -> tuple[Image.Image, bool]:
    """긴 변을 `max_edge` 로 맞춘다.

    지시서 §10 — 실제 서비스에서 클라이언트가 1024px로 줄여 업로드한다.
    평가도 같은 조건으로 해야 숫자가 실제 서비스와 맞는다. 그래서 서버에서도
    한 번 더 적용한다 (이미 작으면 아무 일도 하지 않는다).
    """
    longest = max(image.size)
    if longest <= max_edge:
        return image, False
    scale = max_edge / longest
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(new_size, Image.LANCZOS), True


def assess_quality(image: Image.Image) -> QualityReport:
    """블러와 밝기를 재서 재촬영이 필요한지 판단한다.

    블러는 라플라시안 분산을 쓴다. 초점이 맞으면 경계에서 2차 미분값이 크게
    흔들리고, 흐리면 값이 뭉개져 분산이 작아진다.
    """
    settings = get_settings()
    gray = np.asarray(image.convert("L"), dtype=np.uint8)

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())

    error: ErrorCode | None = None
    # 어두운 사진은 흐릿하게도 측정되므로 밝기를 먼저 본다.
    # 아이에게 "흔들렸어" 대신 "어두워"라고 말해줘야 행동이 교정된다.
    if brightness < settings.min_brightness:
        error = ErrorCode.IMAGE_TOO_DARK
    elif blur_score < settings.min_blur_score:
        error = ErrorCode.IMAGE_TOO_BLURRY

    return QualityReport(blur_score=blur_score, brightness=brightness, error_code=error)


def prepare(payload: bytes) -> PreparedImage:
    """업로드 바이트를 추론 가능한 이미지로 만든다.

    이 함수를 통과한 이미지에는 위치정보가 남아 있지 않다.
    """
    settings = get_settings()

    try:
        source = Image.open(io.BytesIO(payload))
        source.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageDecodeError(f"이미지를 읽을 수 없습니다: {exc}") from exc

    # 2단계 — 회전 보정. EXIF를 지우기 전에 해야 한다.
    rotated = ImageOps.exif_transpose(source)
    if rotated is None:  # exif_transpose는 드물게 None을 준다
        rotated = source
    rotated = rotated.convert("RGB")

    # 클라이언트와 같은 규격으로 줄인다. 큰 이미지를 먼저 줄여야
    # 메타데이터 제거(픽셀 복사)와 품질 검사가 모두 싸진다.
    resized, was_resized = _resize_to_client_spec(rotated, settings.client_max_edge)

    # 3단계 — 메타데이터 제거
    clean = _strip_metadata(resized)

    # 4단계 — 품질 검사
    quality = assess_quality(clean)

    logger.debug(
        "prepare: %dx%d resized=%s blur=%.1f brightness=%.1f -> %s",
        clean.width,
        clean.height,
        was_resized,
        quality.blur_score,
        quality.brightness,
        quality.error_code or "ok",
    )

    return PreparedImage(
        image=clean,
        width=clean.width,
        height=clean.height,
        quality=quality,
        resized=was_resized,
    )
