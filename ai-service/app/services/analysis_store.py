"""분석 결과 보관 — STEP 8의 Before/After 비교를 위한 최소 저장소.

`beforeAnalysisId` 로 Before 판정을 되찾으려면 그 결과를 어딘가 기억해야 한다.

**이미지는 저장하지 않는다.** 품목명과 상태값, 요구했던 행동 코드만 남긴다.
크롭 후 원본을 즉시 폐기한다는 §11-5와 어긋나지 않도록, 픽셀은 이 모듈에
들어오지 않는다.

프로세스 메모리에만 둔다. 서버를 재시작하면 사라지고, 그때는 `beforeAnalysisId`
조회가 실패해 After가 단독 판정으로 떨어진다. 노트북 로컬 서버로 시연하는
현재 배포 형태(지시서 §10)에서는 이 정도로 충분하다. 다중 워커나 재시작 후에도
비교가 필요해지면 여기만 Redis 같은 외부 저장소로 바꾸면 된다.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from app.schemas.enums import ActionCode, StateValue

logger = logging.getLogger(__name__)

#: 보관 기간. 아이가 라벨을 떼고 다시 찍어오는 데 걸리는 시간보다 넉넉해야 한다.
_TTL_SECONDS = 60 * 60

#: 메모리 상한. 넘으면 오래된 것부터 버린다.
_MAX_ENTRIES = 2000

_lock = threading.Lock()


@dataclass(frozen=True)
class Snapshot:
    """Before 시점의 판정. 비교에 필요한 값만 담는다."""

    analysis_id: str
    scan_session_id: str
    item_name_ko: str | None
    class_code: str | None
    states: dict[str, StateValue] = field(default_factory=dict)
    required_actions: list[ActionCode] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


_entries: dict[str, Snapshot] = {}


def _evict_expired(now: float) -> None:
    """만료된 항목 제거. 호출부가 이미 락을 잡고 있어야 한다."""
    stale = [key for key, snap in _entries.items() if now - snap.created_at > _TTL_SECONDS]
    for key in stale:
        del _entries[key]
    if stale:
        logger.debug("만료된 분석 %d건 정리", len(stale))


def save(snapshot: Snapshot) -> None:
    now = time.time()
    with _lock:
        _evict_expired(now)
        if len(_entries) >= _MAX_ENTRIES:
            oldest = min(_entries.values(), key=lambda s: s.created_at)
            del _entries[oldest.analysis_id]
        _entries[snapshot.analysis_id] = snapshot


def get(analysis_id: str) -> Snapshot | None:
    now = time.time()
    with _lock:
        _evict_expired(now)
        return _entries.get(analysis_id)


def clear() -> None:
    """테스트용."""
    with _lock:
        _entries.clear()
