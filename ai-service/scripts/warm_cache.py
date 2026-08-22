"""발표용 캐시 데우기 — STEP 9.

시연할 사진을 미리 한 번 돌려 판정을 저장해 둔다. 그러면 발표 당일

- 와이파이가 끊겨도 (`AI_MODE=cached`)
- API가 느리거나 장애가 나도
- 같은 사진을 몇 번을 눌러도

데모가 멈추지 않고 즉시 응답한다. 캐시 적중 시 응답은 **10ms 안쪽**이다.

    python scripts/warm_cache.py 시연사진/            # 폴더 통째로
    python scripts/warm_cache.py before.jpg after.jpg --pair
    python scripts/warm_cache.py --eval-set           # 동결 평가셋 전량
    python scripts/warm_cache.py --stats              # 지금 상태만 보기
    python scripts/warm_cache.py --clear              # 비우기

**이미지는 저장되지 않는다.** 파일 해시와 판정 JSON만 남는다. (지시서 §11-5)

데운 뒤 `.env` 에서 `AI_MODE=cached` 로 바꾸면 네트워크를 아예 쓰지 않는다.
캐시에 없는 사진은 "지금은 새 사진을 볼 수 없어"로 안내된다.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_settings  # noqa: E402
from app.schemas.request import AnalyzeRequest  # noqa: E402
from app.services import cache, pipeline  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
IMAGES_DIR = BASE_DIR / "eval_frozen" / "images"
CSV_PATH = BASE_DIR / "eval_frozen" / "eval_frozen_labels.csv"


def human(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


def show_stats() -> None:
    s = cache.stats()
    settings = get_settings()
    print(f"캐시 위치 : {settings.cache_dir}")
    print(f"항목 수   : {s['entries']}건")
    print(f"디스크    : {human(s['bytes'])}")


def collect(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES))
        elif p.exists():
            found.append(p)
        else:
            print(f"파일이 없습니다: {p}")
    return found


def eval_set_rows() -> list[tuple[Path, str, str, str | None]]:
    """동결 평가셋을 (경로, phase, pair_id, userChoice)로 읽는다."""
    if not CSV_PATH.exists():
        return []
    choices = {"일반쓰레기(통째로)": "gel", "물 버리고 비닐류": "water"}
    rows = []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fp:
        for r in csv.DictReader(fp):
            path = IMAGES_DIR / r["filename"].strip()
            if not path.exists():
                continue
            phase = {"before": "BEFORE", "after": "AFTER", "single": "SINGLE"}[
                r["phase"].strip().lower()
            ]
            rows.append(
                (path, phase, r.get("pair_id", "").strip(), choices.get(r["expected"].strip()))
            )
    # Before를 먼저 돌려야 After가 비교 대상을 찾는다.
    rows.sort(key=lambda x: (x[2] or x[0].name, 0 if x[1] == "BEFORE" else 1))
    return rows


def warm(path: Path, phase: str, before_id: str | None, choice: str | None):
    req = AnalyzeRequest(
        scanSessionId=f"warm_{path.stem}",
        phase=phase,
        beforeAnalysisId=before_id,
        userChoice=choice,
    )
    return pipeline.run(path.read_bytes(), req)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", help="사진 파일 또는 폴더")
    parser.add_argument("--eval-set", action="store_true", help="동결 평가셋 전량")
    parser.add_argument("--pair", action="store_true", help="두 장을 Before/After 한 쌍으로")
    parser.add_argument("--stats", action="store_true", help="캐시 상태만 보기")
    parser.add_argument("--clear", action="store_true", help="캐시 비우기")
    args = parser.parse_args()

    if args.clear:
        removed = cache.clear()
        print(f"캐시 {removed}건을 비웠습니다.")
        return 0

    if args.stats or (not args.paths and not args.eval_set):
        show_stats()
        if not args.stats:
            print("\n데울 사진을 지정하세요.  예: python scripts/warm_cache.py 시연사진/")
        return 0

    settings = get_settings()
    if settings.ai_mode == "cached":
        print("AI_MODE=cached 에서는 새로 데울 수 없습니다 (네트워크를 쓰지 않는 모드).")
        print(".env 에서 AI_MODE=remote 로 바꾼 뒤 데우고, 다시 cached 로 돌리세요.")
        return 1

    if args.eval_set:
        jobs = eval_set_rows()
        if not jobs:
            print("평가셋 사진이 없습니다.")
            return 1
    else:
        images = collect(args.paths)
        if not images:
            print("처리할 사진이 없습니다.")
            return 1
        if args.pair:
            if len(images) != 2:
                print(f"--pair 는 사진 두 장이 필요합니다 (지금 {len(images)}장)")
                return 1
            jobs = [(images[0], "BEFORE", "pair", None), (images[1], "AFTER", "pair", None)]
        else:
            jobs = [(p, "SINGLE", "", None) for p in images]

    before = cache.stats()
    print(f"{len(jobs)}장 데우기 — 이미 캐시에 있는 사진은 호출하지 않습니다.\n")

    before_ids: dict[str, str] = {}
    hits = calls = failed = 0

    for path, phase, pair_id, choice in jobs:
        started = time.perf_counter()
        try:
            response = warm(
                path, phase, before_ids.get(pair_id) if phase == "AFTER" else None, choice
            )
        except Exception as exc:
            failed += 1
            print(f"  {path.name:<26} 실패 — {exc}")
            continue

        if phase == "BEFORE" and pair_id:
            before_ids[pair_id] = response.analysis_id

        elapsed = time.perf_counter() - started
        if response.processing.cache_hit:
            hits += 1
            mark = "이미 있음"
        elif response.error is not None:
            mark = f"저장 안 함 ({response.error.code})"
        else:
            calls += 1
            mark = "새로 저장"
        print(f"  {path.name:<26} {mark:<28} {elapsed:5.1f}초")

    after = cache.stats()
    print()
    print("=" * 58)
    print(f"새로 저장   : {calls}건 (VLM 호출 {calls}회, 약 ${calls * 0.008:.2f})")
    print(f"이미 있었음 : {hits}건")
    if failed:
        print(f"실패        : {failed}건")
    print(f"캐시 항목   : {before['entries']} → {after['entries']}건")
    print(f"디스크      : {human(before['bytes'])} → {human(after['bytes'])}")
    print()
    print("발표 때는 .env 에서 AI_MODE=cached 로 바꾸면 네트워크를 쓰지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
