"""검출률 진단 — 클래스 순서 확인 + conf 임계값 스윕 + 품질 점수 분포.

검출률이 낮을 때 원인이 (a) 클래스 순서 불일치인지 (b) 임계값이 높은 탓인지
(c) 품질 필터가 과하게 거르는 탓인지 가려낸다. **재학습은 답이 아니다.**
(지시서 §11-1)

    python scripts/diagnose_threshold.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_settings  # noqa: E402
from app.schemas.enums import YOLO_CLASS_ORDER  # noqa: E402
from app.services import preprocess  # noqa: E402
from app.services.detector import _load_model  # noqa: E402

CSV_PATH = BASE_DIR / "eval_frozen" / "eval_frozen_labels.csv"
IMAGES_DIR = BASE_DIR / "eval_frozen" / "images"
SWEEP = [0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]


def main() -> int:
    settings = get_settings()
    model = _load_model()

    # ------------------------------------------------------- 1. 클래스 순서
    print("=" * 62)
    print("1. 클래스 순서 대조 (지시서 §2.2)")
    print("=" * 62)
    names = getattr(model, "names", {})
    loaded = [names[i] for i in sorted(names)] if isinstance(names, dict) else []
    print(f"가중치 : {loaded}")
    print(f"지시서 : {list(YOLO_CLASS_ORDER)}")
    print("일치" if loaded == list(YOLO_CLASS_ORDER) else "!! 불일치 — 라벨이 전부 어긋난다")

    # utf-8-sig — CSV는 Excel 호환을 위해 UTF-8 BOM으로 저장한다.
    rows = [r for r in csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline=""))
            if (IMAGES_DIR / r["filename"].strip()).exists()
            and r["yolo_class"].strip() != "(폴백)"]
    print(f"\n대상 사진 {len(rows)}장 (폴백 제외)")

    # 품질 필터를 끄고 원본 판단력을 본다. 필터 때문에 못 본 것과
    # 모델이 못 찾은 것을 섞으면 원인을 못 가린다.
    print("\n로드 중...", end="", flush=True)
    prepared_all = []
    blur_scores = []
    for row in rows:
        payload = (IMAGES_DIR / row["filename"].strip()).read_bytes()
        prep = preprocess.prepare(payload)
        blur_scores.append((prep.quality.blur_score, prep.quality.brightness,
                            row["filename"].strip()))
        prepared_all.append((row, prep))
    print(" 완료")

    # ------------------------------------------------- 2. conf 임계값 스윕
    print("\n" + "=" * 62)
    print("2. conf 임계값 스윕 (품질 필터 무시, 전량 투입)")
    print("=" * 62)

    # 아주 낮은 conf로 한 번만 추론하고, 이후 임계값은 후처리로 적용한다.
    raw: list[tuple[str, str, list[tuple[str, float]]]] = []
    for row, prep in prepared_all:
        results = model.predict(
            source=prep.image, imgsz=settings.yolo_imgsz, conf=0.01, verbose=False
        )
        preds: list[tuple[str, float]] = []
        for result in results:
            for box in getattr(result, "boxes", []) or []:
                cid = int(box.cls.item())
                if 0 <= cid < len(YOLO_CLASS_ORDER):
                    preds.append((YOLO_CLASS_ORDER[cid], float(box.conf.item())))
        preds.sort(key=lambda p: -p[1])
        raw.append((row["filename"].strip(), row["yolo_class"].strip(), preds))

    print(f"{'conf':>6} {'검출률':>10} {'클래스정확도':>12}")
    print("-" * 32)
    best_line = None
    for threshold in SWEEP:
        hit = 0
        correct = 0
        for _, expected, preds in raw:
            kept = [p for p in preds if p[1] >= threshold]
            if kept:
                hit += 1
                if kept[0][0] == expected:
                    correct += 1
        rate = hit / len(raw)
        acc = correct / len(raw)
        mark = "  ← 현재 설정" if abs(threshold - settings.yolo_conf_threshold) < 1e-9 else ""
        print(f"{threshold:>6.2f} {hit:>4}/{len(raw)} {rate:>5.1%} {correct:>5}/{len(raw)} {acc:>5.1%}{mark}")
        if best_line is None or rate > best_line[1]:
            best_line = (threshold, rate)

    # ------------------------------------ 3. 정답 클래스가 후보에 있었는가
    print("\n" + "=" * 62)
    print("3. 정답 클래스가 후보 목록에 있었나 (conf 무관)")
    print("=" * 62)
    present = sum(1 for _, exp, preds in raw if any(c == exp for c, _ in preds))
    print(f"{present}/{len(raw)} = {present / len(raw):.1%}")
    print("이 값이 높은데 검출률이 낮으면 순전히 임계값 문제다.")

    top_conf_of_correct = [
        max((s for c, s in preds if c == exp), default=0.0) for _, exp, preds in raw
    ]
    nonzero = sorted(s for s in top_conf_of_correct if s > 0)
    if nonzero:
        mid = nonzero[len(nonzero) // 2]
        print(f"정답 클래스 conf 중앙값: {mid:.3f}  (최소 {nonzero[0]:.3f} / 최대 {nonzero[-1]:.3f})")

    # ------------------------------------------------------- 4. 품질 점수
    print("\n" + "=" * 62)
    print("4. 품질 점수 분포 (현재 임계: 블러<%.0f, 밝기<%.0f 면 반려)"
          % (settings.min_blur_score, settings.min_brightness))
    print("=" * 62)
    blur_sorted = sorted(blur_scores)
    print(f"블러 최소 5장: {[f'{b:.0f} ({n})' for b, _, n in blur_sorted[:5]]}")
    rejected = [n for b, _, n in blur_scores if b < settings.min_blur_score]
    print(f"블러로 반려될 사진: {len(rejected)}장 {rejected}")
    dark = [n for _, br, n in blur_scores if br < settings.min_brightness]
    print(f"밝기로 반려될 사진: {len(dark)}장 {dark}")

    # ------------------------------------------------- 5. 품목별 실패 집중도
    print("\n" + "=" * 62)
    print("5. 품목별 — 정답 클래스 최고 conf")
    print("=" * 62)
    by_class: dict[str, list[float]] = defaultdict(list)
    for (_, expected, preds), best_conf in zip(raw, top_conf_of_correct, strict=True):
        by_class[expected].append(best_conf)
    for cls, scores in sorted(by_class.items()):
        found = [s for s in scores if s > 0]
        avg = sum(found) / len(found) if found else 0.0
        print(f"  {cls:<9} n={len(scores):<3} 후보출현 {len(found)}/{len(scores):<3} 평균conf {avg:.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
