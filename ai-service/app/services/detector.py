"""YOLO 검출 — 지시서 §6 파이프라인 6단계.

    conf ≥ 0.35 → 크롭 → VLM
    conf < 0.35 또는 미검출 → 원본 전체를 VLM에 전달 (폴백 경로)

**YOLO는 검출·크롭 담당이며 클래스는 힌트로만 쓴다.** 종류의 최종 판정은 VLM이 한다.
`pack` 클래스 mAP50이 0.310이라 클래스를 결정으로 쓰면 그대로 서비스 오류가 된다.
(지시서 §1, §11-3)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image

from app.core.config import get_settings
from app.schemas.enums import YOLO_CLASS_ORDER

logger = logging.getLogger(__name__)

#: ultralytics 모델은 스레드 안전하지 않다. FastAPI 워커가 동시에 부를 수 있으므로 직렬화한다.
_predict_lock = threading.Lock()


@dataclass(frozen=True)
class Box:
    """0~1 정규화 좌표. 원본 해상도에 독립적이다."""

    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    def overlap_ratio(self, other: Box) -> float:
        """겹친 넓이 ÷ 더 작은 박스의 넓이.

        IoU 대신 이걸 쓴다. 한 물체에 큰 박스와 작은 박스가 겹쳐 잡히는 경우
        (캔 몸통과 캔 뚜껑, 포스터와 그 안에 인쇄된 사진) IoU는 작게 나오지만
        작은 박스는 큰 박스 안에 거의 다 들어가 있다. 그 포함 관계를 봐야 한다.
        """
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.width, other.x + other.width)
        bottom = min(self.y + self.height, other.y + other.height)
        if right <= left or bottom <= top:
            return 0.0
        intersection = (right - left) * (bottom - top)
        smaller = min(self.area, other.area)
        return intersection / smaller if smaller > 0 else 0.0


@dataclass(frozen=True)
class Candidate:
    class_code: str
    confidence: float
    box: Box


@dataclass(frozen=True)
class DetectionResult:
    """검출 결과.

    `best` 가 None이면 폴백 경로(원본을 VLM에 직접 전달)로 간다.
    """

    best: Candidate | None
    candidates: list[Candidate]
    #: 신뢰도 임계값을 넘긴 물체가 둘 이상인지. MULTIPLE_OBJECTS 판단 근거.
    multiple_objects: bool

    @property
    def has_crop_target(self) -> bool:
        return self.best is not None


class WeightsNotFoundError(FileNotFoundError):
    """가중치 파일이 없다. 재학습하지 말고 팀 드라이브에서 받아온다."""


@lru_cache(maxsize=1)
def _load_model():
    """모델을 한 번만 로드한다. 첫 호출에서 수 초 걸린다."""
    settings = get_settings()
    path = settings.yolo_weights_path
    if not path.exists():
        raise WeightsNotFoundError(
            f"YOLO 가중치가 없습니다: {path}\n"
            "dasibom_v1_best.pt 를 app/models/weights/ 에 두세요. (재학습 금지)"
        )

    from ultralytics import YOLO  # 무거우므로 실제로 쓸 때만 임포트한다

    logger.info("YOLO 가중치 로드: %s", path)
    model = YOLO(str(path))

    # 학습 시 클래스 순서와 지시서 §2.2가 어긋나면 이후 전부 잘못된 라벨을 단다.
    # 조용히 틀리느니 기동 시점에 드러내는 편이 낫다.
    names = getattr(model, "names", None)
    if isinstance(names, dict):
        loaded = [names[i] for i in sorted(names)]
        if loaded != list(YOLO_CLASS_ORDER):
            logger.warning(
                "가중치의 클래스 순서가 지시서 §2.2와 다릅니다.\n"
                "  가중치: %s\n  지시서: %s",
                loaded,
                list(YOLO_CLASS_ORDER),
            )
    return model


def _to_box(xyxy, width: int, height: int) -> Box:
    x1, y1, x2, y2 = (float(v) for v in xyxy)
    # 모델이 이미지 밖으로 살짝 넘치는 좌표를 줄 수 있어 잘라낸다.
    x1, x2 = max(0.0, x1), min(float(width), x2)
    y1, y2 = max(0.0, y1), min(float(height), y2)
    return Box(
        x=x1 / width,
        y=y1 / height,
        width=max(0.0, x2 - x1) / width,
        height=max(0.0, y2 - y1) / height,
    )


def detect(image: Image.Image) -> DetectionResult:
    """이미지 한 장에서 폐기물 후보를 찾는다."""
    settings = get_settings()
    model = _load_model()

    with _predict_lock:
        results = model.predict(
            source=image,
            imgsz=settings.yolo_imgsz,
            conf=settings.yolo_conf_threshold,
            verbose=False,
        )

    candidates: list[Candidate] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            class_id = int(box.cls.item())
            if not 0 <= class_id < len(YOLO_CLASS_ORDER):
                logger.warning("범위 밖 클래스 id: %s", class_id)
                continue
            candidates.append(
                Candidate(
                    class_code=YOLO_CLASS_ORDER[class_id],
                    confidence=float(box.conf.item()),
                    box=_to_box(box.xyxy[0].tolist(), image.width, image.height),
                )
            )

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    best = candidates[0] if candidates else None

    # 여러 물체 판단은 개수가 아니라 크기로 한다. 배경에 작게 걸린 물체까지
    # 세면 정상 사진이 계속 반려되어 아이가 이탈한다.
    #
    # 크기만 보면 부족했다. 한 물체에 박스가 겹쳐 잡히는 경우가 흔하다 —
    # 캔 몸통과 뚜껑, 라미네이팅 포스터와 그 안에 인쇄된 사진. 실측에서
    # 정상 사진이 이 경로로 MULTIPLE_OBJECTS 반려를 받았다.
    # 그래서 **겹치지 않는** 경쟁 박스만 다른 물체로 센다.
    multiple = False
    if best is not None:
        rivals = [
            c
            for c in candidates[1:]
            if c.box.area >= best.box.area * settings.multiple_object_area_ratio
            and c.box.overlap_ratio(best.box) < settings.multiple_object_overlap_ratio
        ]
        multiple = bool(rivals)

    logger.info(
        "detect: %d개 후보, best=%s conf=%.3f multiple=%s",
        len(candidates),
        best.class_code if best else "없음",
        best.confidence if best else 0.0,
        multiple,
    )
    return DetectionResult(best=best, candidates=candidates, multiple_objects=multiple)
