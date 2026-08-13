"""이미지 해시 캐시 — 지시서 §6 파이프라인 7단계, STEP 9.

같은 사진을 다시 넣으면 VLM을 부르지 않고 저장된 판정을 돌려준다.

목적이 두 가지다.

1. **발표장 안정성.** 시연할 사진을 미리 돌려 캐시에 넣어두면, 당일 와이파이가
   끊기거나 API가 느려도 데모가 멈추지 않는다. `AI_MODE=cached` 는 아예 네트워크를
   쓰지 않는다.
2. **반복 비용 0.** 같은 사진으로 프론트·백엔드를 붙이며 수십 번 눌러도
   API 호출이 한 번뿐이다.

**이미지는 저장하지 않는다.** 파일 해시(내용 → 64자 문자열)와 판정 JSON만 남는다.
해시에서 원본 픽셀을 되돌릴 수 없으므로, 크롭 후 원본을 폐기한다는 §11-5와
어긋나지 않는다.

지시서는 캐시 조회를 YOLO 다음(7단계)에 두지만 여기서는 **맨 앞**에서 조회한다.
키가 원본 이미지 해시라 앞에서 봐도 결과가 같고, 전처리·검출·얼굴 검출까지
통째로 건너뛸 수 있다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path

from app.core.config import get_settings
from app.schemas.request import AnalyzeRequest
from app.schemas.response import AnalyzeResponse

logger = logging.getLogger(__name__)

_lock = threading.Lock()

#: 저장 형식이 바뀌면 올린다. 옛 항목은 키가 달라져 자연히 무시된다.
_CACHE_FORMAT = "v1"


def _key(payload: bytes, req: AnalyzeRequest) -> str:
    """같은 사진이라도 요청 조건이 다르면 결과가 다르므로 함께 묶는다.

    - `phase` — Before/After에 따라 상태와 비교 결과가 달라진다
    - `regionCode` — 지자체마다 배출 기준이 다르다
    - `userChoice` — 아이스팩 젤/물처럼 사용자 선택으로 결론이 갈린다
    """
    digest = hashlib.sha256(payload).hexdigest()
    parts = [
        _CACHE_FORMAT,
        digest,
        str(req.phase),
        req.region_code,
        req.user_choice or "-",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _path(key: str) -> Path:
    settings = get_settings()
    # 앞 2자로 하위 폴더를 나눈다. 한 폴더에 파일 수천 개가 쌓이면 느려진다.
    return settings.cache_dir / key[:2] / f"{key}.json"


def get(payload: bytes, req: AnalyzeRequest) -> AnalyzeResponse | None:
    """저장된 판정을 찾는다. 없으면 None."""
    path = _path(_key(payload, req))
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fp:
            data = json.load(fp)
        return AnalyzeResponse.model_validate(data)
    except Exception as exc:
        # 캐시가 깨졌다고 서비스가 멈추면 안 된다. 지우고 새로 계산한다.
        logger.warning("캐시 항목을 읽지 못해 폐기합니다: %s (%s)", path.name, exc)
        path.unlink(missing_ok=True)
        return None


def put(payload: bytes, req: AnalyzeRequest, response: AnalyzeResponse) -> None:
    """판정을 저장한다.

    거부·실패 응답은 저장하지 않는다. 흔들린 사진이나 일시적 타임아웃을 캐시에
    박아두면 다시 찍어도 같은 실패가 되돌아온다.
    """
    if response.error is not None:
        return

    path = _path(_key(payload, req))
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fp:
                json.dump(response.model_dump(by_alias=True, mode="json"), fp, ensure_ascii=False)
            tmp.replace(path)  # 원자적 교체 — 반쯤 쓰인 파일이 읽히지 않게
    except OSError as exc:
        logger.warning("캐시 저장 실패(무시하고 진행): %s", exc)


def stats() -> dict[str, int]:
    settings = get_settings()
    if not settings.cache_dir.exists():
        return {"entries": 0, "bytes": 0}
    files = list(settings.cache_dir.rglob("*.json"))
    return {"entries": len(files), "bytes": sum(f.stat().st_size for f in files)}


def clear() -> int:
    """캐시를 비운다. 지운 항목 수를 돌려준다."""
    settings = get_settings()
    if not settings.cache_dir.exists():
        return 0
    files = list(settings.cache_dir.rglob("*.json"))
    with _lock:
        for f in files:
            f.unlink(missing_ok=True)
    return len(files)
