"""동결 평가셋 점검 — CSV와 실제 사진 파일을 대조한다.

사진이 계속 들어오는 동안 "지금 몇 장이 준비됐고 무엇이 비었는지"를 확인하는 용도다.
STEP 6 평가 스크립트를 돌리기 전에 이걸 먼저 통과시킨다.

    python scripts/check_eval_assets.py

표준 라이브러리만 쓴다. 사진 해상도까지 보려면 Pillow가 있어야 하지만,
없으면 그 항목만 건너뛴다.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = BASE_DIR / "eval_frozen" / "eval_frozen_labels.csv"
IMAGES_DIR = BASE_DIR / "eval_frozen" / "images"

#: 지시서 §7.1 — 동결 평가셋의 목표 규모.
#:
#: 원래 110행(before 41 / after 41 / single 28)이었다. 우유팩과 플라스틱 음료병
#: before/after 20행은 촬영하지 못해 평가셋에서 뺐다. 두 품목 모두 도감과 AI
#: 판정에는 그대로 남아 있고, 정확도를 측정할 사진이 없다는 뜻일 뿐이다.
#: 사진을 찍으면 행을 되살리고 이 값도 되돌린다.
TARGET_TOTAL = 90
TARGET_BY_PHASE = {"before": 31, "after": 31, "single": 28}

#: 지시서 §10 — 클라이언트가 긴 변 1024px로 리사이즈해 업로드한다.
#: 평가도 같은 조건으로 해야 숫자가 실제 서비스와 맞는다.
CLIENT_MAX_EDGE = 1024

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


#: CSV는 UTF-8 BOM으로 저장한다. 한글 Windows의 Excel은 BOM이 없으면 CP949로
#: 읽어서 한글이 깨진다. `utf-8-sig` 로 읽으면 BOM이 있든 없든 처리된다.
#: (`utf-8` 로 읽으면 BOM이 첫 컬럼명에 붙어 "﻿filename" 이 된다)
CSV_ENCODING = "utf-8-sig"


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding=CSV_ENCODING, newline="") as fp:
        return list(csv.DictReader(fp))


def actual_images() -> set[str]:
    if not IMAGES_DIR.exists():
        return set()
    return {
        p.name
        for p in IMAGES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    }


def heading(text: str) -> None:
    print(f"\n{text}")
    print("-" * len(text))


def main() -> int:
    if not CSV_PATH.exists():
        print(f"CSV 없음: {CSV_PATH}")
        return 1

    rows = load_rows()
    files = actual_images()
    csv_names = [r["filename"].strip() for r in rows]

    problems = 0

    # ---------------------------------------------------------------- 규모
    heading("1. 규모")
    print(f"CSV 행 수      : {len(rows)} / 목표 {TARGET_TOTAL}")
    phase_counts = Counter(r["phase"].strip().lower() for r in rows)
    for phase, target in TARGET_BY_PHASE.items():
        got = phase_counts.get(phase, 0)
        mark = "OK" if got == target else "!!"
        print(f"  {phase:<7}: {got:>3} / {target:<3} {mark}")
    print(f"실제 사진 파일 : {len(files)}장")

    # ------------------------------------------------------- CSV ↔ 파일 대조
    heading("2. CSV ↔ 파일 대조")
    missing = [n for n in csv_names if n not in files]
    orphan = sorted(files - set(csv_names))

    print(f"CSV에 있으나 파일 없음 : {len(missing)}건  (촬영 대기)")
    print(f"파일은 있으나 CSV 없음 : {len(orphan)}건  (라벨 누락)")

    if missing:
        by_item: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            if row["filename"].strip() in missing:
                by_item[row["item"].strip()].append(row["filename"].strip())
        print("\n  [촬영 대기] 품목별")
        for item, names in sorted(by_item.items(), key=lambda kv: -len(kv[1])):
            print(f"    {item:<16} {len(names):>3}장")
            for name in sorted(names):
                print(f"        - {name}")
        problems += 1

    if orphan:
        print("\n  [라벨 누락] CSV에 행을 추가해야 하는 파일")
        for name in orphan:
            print(f"    - {name}")
        problems += 1

    # ------------------------------------------------------------ 중복 검사
    heading("3. 파일명 중복")
    duplicates = [name for name, count in Counter(csv_names).items() if count > 1]
    if duplicates:
        print("같은 filename이 여러 행에 있다. 평가 시 매칭이 어긋난다.")
        for name in duplicates:
            print(f"  - {name}")
        problems += 1
    else:
        print("중복 없음")

    # 확장자만 다르고 이름이 같은 경우. `coated (1).jpeg/.jpg/.png` 처럼
    # 서로 다른 사진인데 이름을 재활용했을 가능성이 크다.
    stems: dict[str, list[str]] = defaultdict(list)
    for name in csv_names:
        stems[Path(name).stem].append(name)
    collisions = {s: ns for s, ns in stems.items() if len(set(ns)) > 1}
    if collisions:
        print("\n확장자만 다른 동명 파일 (의도한 것인지 확인 필요)")
        for stem, names in collisions.items():
            print(f"  - {stem}: {', '.join(sorted(set(names)))}")

    # ------------------------------------------------- prompt_examples 격리
    heading("4. prompt_examples 격리 (지시서 §7.1)")
    examples_dir = BASE_DIR / "prompt_examples"
    example_files = (
        {p.name for p in examples_dir.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES}
        if examples_dir.exists()
        else set()
    )
    overlap = example_files & files
    if overlap:
        print("겹침 발견. few-shot 예시가 평가셋에 들어가면 성능 수치가 무효가 된다.")
        for name in sorted(overlap):
            print(f"  - {name}")
        problems += 1
    else:
        print(f"겹침 없음 (prompt_examples 이미지 {len(example_files)}장)")

    # ---------------------------------------------------------- 해상도 확인
    heading("5. 해상도")
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:
        print("Pillow 미설치 — 건너뜀 (STEP 2에서 설치된다)")
    else:
        oversized = []
        for name in sorted(files):
            try:
                with Image.open(IMAGES_DIR / name) as img:
                    if max(img.size) > CLIENT_MAX_EDGE:
                        oversized.append((name, img.size))
            except Exception as exc:  # 손상된 파일도 여기서 드러난다
                print(f"  읽기 실패: {name} ({exc})")
                problems += 1
        if oversized:
            print(
                f"긴 변 {CLIENT_MAX_EDGE}px 초과: {len(oversized)}장.\n"
                "  원본을 지우지 말 것. 평가 시 파이프라인이 업로드와 같은 조건으로\n"
                "  리사이즈해서 넣는다. (지시서 §10)"
            )
        else:
            print(f"전부 긴 변 {CLIENT_MAX_EDGE}px 이하")

    # ---------------------------------------------------------------- 요약
    heading("요약")
    ready = len([n for n in csv_names if n in files])
    print(f"평가 가능한 행: {ready} / {len(rows)}  ({ready * 100 // max(len(rows), 1)}%)")
    if problems:
        print(f"확인이 필요한 항목 {problems}종. 위 내용을 참고할 것.")
    else:
        print("이상 없음. STEP 6 평가를 돌릴 수 있다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
