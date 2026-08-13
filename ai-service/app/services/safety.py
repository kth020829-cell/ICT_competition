"""안전 필터 — 지시서 §6 파이프라인 5단계, §11-5.

    얼굴이 하나라도 검출되면 REJECTED / FACE_DETECTED.

아동 개인정보 보호가 목적이다. 촬영자 본인이든 배경의 다른 아이든 구분하지
않는다. 얼굴이 보이면 분석하지 않고 재촬영을 요구한다.

**이 단계는 YOLO 검출·크롭보다 먼저 돈다.** 크롭이 얼굴을 잘라내 버리면
"얼굴이 찍혔다"는 사실 자체를 놓치기 때문이다. 원본 전체를 보고 판단해야 한다.

모델은 MediaPipe BlazeFace(short-range)다. mediapipe 1.0.0에서 레거시
`solutions` API가 제거되어 Tasks API를 쓴다. Tasks API는 `.tflite` 파일을
직접 요구하므로 가중치를 저장소에 함께 둔다(224KB, Apache-2.0).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: mediapipe FaceDetector도 스레드 안전하지 않다. detector와 같은 이유로 직렬화한다.
_detect_lock = threading.Lock()


@dataclass(frozen=True)
class FaceCheck:
    """얼굴 검출 결과."""

    face_count: int
    #: 가장 확신이 큰 얼굴의 점수. 검출이 없으면 0.0.
    top_score: float

    @property
    def has_face(self) -> bool:
        return self.face_count > 0


class FaceModelNotFoundError(FileNotFoundError):
    """BlazeFace 가중치가 없다.

    이 경우 '얼굴이 없다'고 단정할 수 없다. 조용히 통과시키면 아동 얼굴이
    그대로 VLM으로 넘어가므로, 호출부는 503으로 서비스 미준비를 알린다.
    """


@lru_cache(maxsize=1)
def _load_detector():
    """FaceDetector를 한 번만 만든다."""
    settings = get_settings()
    path = settings.face_model_path
    if not path.exists():
        raise FaceModelNotFoundError(
            f"BlazeFace 가중치가 없습니다: {path}\n"
            "저장소에 포함되어 있습니다. git pull 로 받아오세요."
        )

    # mediapipe는 무겁고 import에 수 초가 걸린다. 실제로 쓸 때만 가져온다.
    from mediapipe.tasks.python import BaseOptions  # noqa: PLC0415
    from mediapipe.tasks.python.vision import (  # noqa: PLC0415
        FaceDetector,
        FaceDetectorOptions,
        RunningMode,
    )

    logger.info("BlazeFace 가중치 로드: %s", path)
    return FaceDetector.create_from_options(
        FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=RunningMode.IMAGE,
            min_detection_confidence=settings.face_min_confidence,
        )
    )


def detect_faces(image: Image.Image) -> FaceCheck:
    """이미지에서 얼굴을 찾는다.

    임계값을 낮게 두는 편이 안전하다. 얼굴을 놓쳐서 통과시키는 쪽이
    잘못 걸러서 재촬영을 시키는 쪽보다 훨씬 나쁘다.
    """
    import mediapipe as mp  # noqa: PLC0415

    detector = _load_detector()
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    with _detect_lock:
        result = detector.detect(mp_image)

    detections = getattr(result, "detections", None) or []
    scores: list[float] = []
    for det in detections:
        categories = getattr(det, "categories", None) or []
        if categories:
            scores.append(float(categories[0].score))

    check = FaceCheck(
        face_count=len(detections),
        top_score=max(scores) if scores else 0.0,
    )
    if check.has_face:
        logger.info("얼굴 %d개 검출 (top=%.3f) → 분석 거부", check.face_count, check.top_score)
    return check
