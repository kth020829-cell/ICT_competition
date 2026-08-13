"""STEP 2 스모크 테스트 — 실제 사진으로 전처리 + 검출을 돌려본다.

    python scripts/smoke_detect.py            # eval_frozen 사진 전량
    python scripts/smoke_detect.py --limit 10

YOLO 클래스 정확도는 **참고 지표다.** 틀려도 VLM이 교정하므로 서비스 영향은 작다.
여기서 중요한 것은 "크롭이 생성되는가"(검출률)다. (지시서 §7.3)
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.services import cropper, detector, preprocess  # noqa: E402

CSV_PATH = BASE_DIR / "eval_frozen" / "eval_frozen_labels.csv"
IMAGES_DIR = BASE_DIR / "eval_frozen" / "images"

#: 폴백 4종은 YOLO 미대응이라 검출률 계산에서 제외한다. (지시서 §7.3-1)
FALLBACK_MARK = "(폴백)"


#: Excel 호환을 위해 CSV는 UTF-8 BOM으로 저장한다. utf-8-sig가 BOM을 벗겨준다.
CSV_ENCODING = "utf-8-sig"


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding=CSV_ENCODING, newline="") as fp:
        return list(csv.DictReader(fp))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="처리할 장수 (0=전체)")
    args = parser.parse_args()

    rows = [r for r in load_rows() if (IMAGES_DIR / r["filename"].strip()).exists()]
    if args.limit:
        rows = rows[: args.limit]

    if not rows:
        print("처리할 사진이 없습니다. eval_frozen/images/ 를 확인하세요.")
        return 1

    print(f"{len(rows)}장 처리\n")

    detected = 0
    evaluable = 0          # 폴백 제외 — 검출률 분모
    class_correct = 0
    quality_failures: Counter[str] = Counter()
    per_item: dict[str, list[bool]] = defaultdict(list)
    elapsed_total = 0.0
    misses: list[str] = []

    header = f"{'파일':<26} {'기대':<9} {'검출':<9} {'conf':>6} {'ms':>6}"
    print(header)
    print("-" * len(header))

    for row in rows:
        name = row["filename"].strip()
        expected = row["yolo_class"].strip()
        is_fallback = expected == FALLBACK_MARK

        payload = (IMAGES_DIR / name).read_bytes()
        started = time.perf_counter()

        prepared = preprocess.prepare(payload)
        if not prepared.quality.ok:
            quality_failures[prepared.quality.error_code] += 1
            print(f"{name:<26} {expected:<9} {'품질미달':<9} {'-':>6} {'-':>6}"
                  f"  ({prepared.quality.error_code})")
            continue

        result = detector.detect(prepared.image)
        got = result.best.class_code if result.best else "-"
        conf = result.best.confidence if result.best else 0.0

        # 크롭까지 실제로 만들어본다. 여기서 터지면 STEP 4가 못 돈다.
        if result.best:
            crop = cropper.crop(prepared.image, result.best.box)
            assert crop.width >= 2 and crop.height >= 2

        elapsed = (time.perf_counter() - started) * 1000
        elapsed_total += elapsed

        if not is_fallback:
            evaluable += 1
            if result.best:
                detected += 1
                if got == expected:
                    class_correct += 1
            else:
                misses.append(f"{name} (기대 {expected})")
            per_item[row["item"].strip()].append(result.best is not None)

        print(f"{name:<26} {expected:<9} {got:<9} {conf:>6.3f} {elapsed:>6.0f}")

    # ------------------------------------------------------------------ 요약
    print("\n" + "=" * 60)
    print("요약")
    print("=" * 60)
    if evaluable:
        print(f"검출률 (크롭 생성)  : {detected}/{evaluable} = {detected / evaluable:.1%}")
        print(f"클래스 정확도(참고) : {class_correct}/{evaluable} = {class_correct / evaluable:.1%}")
    print(f"평균 처리 시간      : {elapsed_total / max(len(rows), 1):.0f} ms/장")
    if quality_failures:
        print("\n품질 미달")
        for code, count in quality_failures.most_common():
            print(f"  {code}: {count}장")

    print("\n품목별 검출률")
    for item, flags in sorted(per_item.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        rate = sum(flags) / len(flags)
        print(f"  {item:<18} {sum(flags):>2}/{len(flags):<3} {rate:>6.1%}")

    if misses:
        print(f"\n미검출 {len(misses)}장 (VLM 단독 경로로 라우팅된다)")
        for miss in misses:
            print(f"  - {miss}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
