"""크롭 — 지시서 §6 파이프라인 7단계.

> **크롭 후 원본 즉시 폐기.** 배경에 다른 아이 얼굴이 들어갈 수 있으므로,
> 크롭 이미지만 VLM에 전달한다.

이 모듈의 존재 이유가 그 규칙이다. `crop_and_discard()` 는 크롭만 돌려주고
원본으로 가는 참조를 끊는다. 호출부는 원본을 따로 붙들지 않는다.
"""

from __future__ import annotations

import logging

from PIL import Image

from app.core.config import get_settings
from app.services.detector import Box

logger = logging.getLogger(__name__)


def crop(image: Image.Image, box: Box, *, padding: float | None = None) -> Image.Image:
    """정규화 박스로 잘라낸다.

    박스에 여백을 조금 준다. YOLO 박스가 물체에 딱 붙으면 라벨 가장자리나
    뚜껑이 잘려 나가는데, 그것들이 바로 VLM이 판정해야 할 대상이다.
    """
    settings = get_settings()
    pad = settings.crop_padding if padding is None else padding

    width, height = image.size
    left = (box.x - box.width * pad) * width
    top = (box.y - box.height * pad) * height
    right = (box.x + box.width * (1 + pad)) * width
    bottom = (box.y + box.height * (1 + pad)) * height

    # 이미지 경계를 벗어나지 않게 자른다.
    left = max(0, int(round(left)))
    top = max(0, int(round(top)))
    right = min(width, int(round(right)))
    bottom = min(height, int(round(bottom)))

    # 박스가 뭉개진 경우(폭·높이 0) 원본 전체로 되돌린다. 빈 이미지를 VLM에
    # 넘기는 것보다 낫다.
    if right - left < 2 or bottom - top < 2:
        logger.warning("크롭 영역이 너무 작아 원본 전체를 사용합니다: %s", box)
        return image.copy()

    return image.crop((left, top, right, bottom))


def crop_and_discard(image: Image.Image, box: Box) -> Image.Image:
    """크롭본을 만들고 원본 버퍼를 닫는다.

    반환값은 원본과 메모리를 공유하지 않는다. 호출부에서 원본 변수를 다시 쓰지
    않는 한, 이 시점 이후로 배경이 포함된 픽셀은 남지 않는다.
    """
    cropped = crop(image, box).copy()
    try:
        image.close()
    except Exception:  # 이미 닫혔거나 close를 지원하지 않는 경우
        logger.debug("원본 close 생략", exc_info=True)
    logger.debug("크롭 완료: %dx%d, 원본 폐기", cropped.width, cropped.height)
    return cropped
