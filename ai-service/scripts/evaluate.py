"""STEP 6 — 동결 평가셋 측정 (지시서 §7.3).

    python scripts/evaluate.py                 # 준비된 사진 전량
    python scripts/evaluate.py --limit 10      # 앞에서 10장만
    python scripts/evaluate.py --item 투명 페트병   # 특정 품목만
    python scripts/evaluate.py --no-vlm        # YOLO까지만 (VLM 호출 없음, 무료)

지시서 §7.3이 요구하는 7개 지표를 산출한다.

    1. YOLO 검출률        — 크롭이 생성된 비율 (폴백 4종 제외)
    2. YOLO 클래스 정확도  — 참고 지표. 틀려도 VLM이 교정한다
    3. VLM 품목 정확도    — itemNameKo가 CSV item과 일치
    4. VLM 상태 정확도    — states가 CSV state와 일치
    5. 최종 결론 정확도   — **가장 중요**. expected와 일치하는 비율
    6. Before/After 판정  — improvedActions가 실제 변화와 일치
    7. 응답 시간 · VLM 호출 횟수 · 캐시 히트율

**이 데이터는 학습이나 few-shot 예시로 절대 쓰지 않는다.** (지시서 §11-2)
여기서 나온 숫자가 프로젝트의 유일한 성능 근거다.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.schemas.enums import (  # noqa: E402
    DISPOSAL_NAME_KO,
    ITEM_TO_CLASS,
    AnalysisStatus,
    DisposalCategory,
    StateValue,
)
from app.schemas.request import AnalyzeRequest  # noqa: E402
from app.services import detector, pipeline, preprocess  # noqa: E402

CSV_PATH = BASE_DIR / "eval_frozen" / "eval_frozen_labels.csv"
IMAGES_DIR = BASE_DIR / "eval_frozen" / "images"
CSV_ENCODING = "utf-8-sig"

#: 폴백 4종은 YOLO 미대응이라 검출률 계산에서 제외한다. (지시서 §7.3-1)
FALLBACK_MARK = "(폴백)"

#: Before 행의 정답. 배출 결론이 아니라 준비 안내다. (지시서 §4.3)
EXPECT_ACTION_REQUIRED = "준비 필요 안내"

#: CSV의 expected 문자열 → 배출 분류.
#: 공백 표기가 코드값과 미묘하게 달라(투명페트병 / 투명 페트병) 직접 대응시킨다.
EXPECTED_TO_DISPOSAL: dict[str, DisposalCategory] = {
    "일반쓰레기": DisposalCategory.GENERAL_WASTE,
    "일반쓰레기(통째로)": DisposalCategory.GENERAL_WASTE,
    "플라스틱": DisposalCategory.PLASTIC_BIN,
    "종이류": DisposalCategory.PAPER_BIN,
    "투명페트병 전용함": DisposalCategory.CLEAR_PET_BIN,
    "종이팩 전용함": DisposalCategory.PAPER_PACK_BIN,
    "캔류": DisposalCategory.CAN_BIN,
    "비닐류": DisposalCategory.VINYL_BIN,
    "폐건전지 전용 수거함": DisposalCategory.BATTERY_BIN,
    "물 버리고 비닐류": DisposalCategory.VINYL_BIN,
}

#: 아이스팩처럼 사용자 선택이 필요한 행은 expected에서 선택값을 역산한다.
EXPECTED_TO_USER_CHOICE: dict[str, str] = {
    "일반쓰레기(통째로)": "gel",
    "물 버리고 비닐류": "water",
}

#: CSV의 품목 표기 → 도감 품목명.
#:
#: 촬영 담당이 설명을 덧붙여 적은 경우가 있다. 표기 차이를 오답으로 세면
#: 품목 정확도가 실제보다 낮게 나온다. 여기서 흡수하되, 대응되지 않는 이름은
#: 실행 끝에 경고로 남겨 CSV를 고칠 수 있게 한다.
ITEM_ALIASES: dict[str, str] = {
    "코팅지(라미네이팅)": "코팅지",
}


def canonical_item(raw: str) -> str:
    name = raw.strip()
    return ITEM_ALIASES.get(name, name)


#: CSV state 자유 문자열 → 기대 상태값.
#:
#: 촬영자가 사람 말로 적은 기록이라 키워드로 옮긴다. 여기 없는 표현은
#: 채점하지 않는다(모르는 것을 틀렸다고 하지 않는다).
STATE_KEYWORDS: list[tuple[str, str, StateValue]] = [
    ("라벨 부착", "labelAttached", StateValue.YES),
    ("라벨 제거", "labelAttached", StateValue.NO),
    ("뚜껑 있음", "capAttached", StateValue.YES),
    ("뚜껑 닫음", "capAttached", StateValue.YES),
    ("뚜껑 제거", "capAttached", StateValue.NO),
    ("뚜껑 분리", "capAttached", StateValue.NO),
    ("내용물 잔여", "contentRemaining", StateValue.YES),
    ("세척 완료", "contentRemaining", StateValue.NO),
    ("헹굼 완료", "contentRemaining", StateValue.NO),
    ("헹굼 완료", "rinsed", StateValue.YES),
    ("압착", "flattened", StateValue.YES),
    ("압축", "flattened", StateValue.YES),
    ("펼쳐서 말림", "unfolded", StateValue.YES),
    ("접힌 상태", "unfolded", StateValue.NO),
    ("테이프·송장 부착", "tapeAttached", StateValue.YES),
    ("테이프·송장 제거", "tapeAttached", StateValue.NO),
    ("국물·건더기 잔여", "contaminated", StateValue.YES),
    ("양념 잔여", "contaminated", StateValue.YES),
    ("끈적임", "contaminated", StateValue.YES),
    ("세척 완료", "contaminated", StateValue.NO),
]


def expected_states(raw: str) -> dict[str, StateValue]:
    """CSV state 문자열에서 채점 가능한 상태만 뽑는다."""
    text = raw.strip()
    if not text or text == "-":
        return {}
    found: dict[str, StateValue] = {}
    for keyword, key, value in STATE_KEYWORDS:
        if keyword in text:
            found.setdefault(key, value)
    return found


@dataclass
class Counter:
    hit: int = 0
    total: int = 0

    def add(self, ok: bool) -> None:
        self.total += 1
        self.hit += int(ok)

    @property
    def rate(self) -> float:
        return self.hit / self.total if self.total else 0.0

    def __str__(self) -> str:
        if not self.total:
            return "  -  (해당 없음)"
        return f"{self.hit}/{self.total} = {self.rate:.1%}"


@dataclass
class Metrics:
    detection: Counter = field(default_factory=Counter)
    yolo_class: Counter = field(default_factory=Counter)
    vlm_item: Counter = field(default_factory=Counter)
    vlm_state: Counter = field(default_factory=Counter)
    conclusion: Counter = field(default_factory=Counter)
    before_after: Counter = field(default_factory=Counter)
    elapsed_ms: list[int] = field(default_factory=list)
    vlm_calls: int = 0
    cache_hits: int = 0
    per_item: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    misses: list[str] = field(default_factory=list)
    unmapped_expected: set[str] = field(default_factory=set)
    unknown_items: set[str] = field(default_factory=set)
    error_codes: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding=CSV_ENCODING, newline="") as fp:
        return list(csv.DictReader(fp))


def judge_conclusion(row: dict[str, str], response, metrics: Metrics) -> bool:
    """5번 지표 — 최종 결론이 CSV expected와 맞는지."""
    expected = row["expected"].strip()

    # Before의 정답은 배출 결론이 아니라 '준비 필요 안내'다. (지시서 §4.3)
    if expected == EXPECT_ACTION_REQUIRED:
        return response.status == AnalysisStatus.ACTION_REQUIRED

    category = EXPECTED_TO_DISPOSAL.get(expected)
    if category is None:
        metrics.unmapped_expected.add(expected)
        return False

    if response.disposal is None:
        return False
    return response.disposal.category_code == category


def run_one(row: dict[str, str], *, before_id: str | None, use_vlm: bool):
    """사진 한 장을 파이프라인에 태운다."""
    name = row["filename"].strip()
    phase_raw = row["phase"].strip().lower()
    phase = {"before": "BEFORE", "after": "AFTER", "single": "SINGLE"}[phase_raw]

    req = AnalyzeRequest(
        scanSessionId=f"eval_{row.get('pair_id') or name}",
        phase=phase,
        beforeAnalysisId=before_id,
        userChoice=EXPECTED_TO_USER_CHOICE.get(row["expected"].strip()),
    )
    payload = (IMAGES_DIR / name).read_bytes()

    if not use_vlm:
        return None
    return pipeline.run(payload, req)


def yolo_only(row: dict[str, str], metrics: Metrics) -> None:
    """1·2번 지표는 YOLO 단독으로 잰다.

    응답의 classCode는 VLM 판정에서 나오므로(지시서 §11-3) YOLO 자체 성능을
    보려면 검출기를 따로 돌려야 한다. 평가 전용 경로다.
    """
    name = row["filename"].strip()
    expected_class = row["yolo_class"].strip()
    if expected_class == FALLBACK_MARK:
        return

    prepared = preprocess.prepare((IMAGES_DIR / name).read_bytes())
    if not prepared.quality.ok:
        metrics.detection.add(False)
        metrics.yolo_class.add(False)
        return

    result = detector.detect(prepared.image)
    metrics.detection.add(result.has_crop_target)
    metrics.yolo_class.add(bool(result.best) and result.best.class_code == expected_class)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="처리할 장수 (0=전체)")
    parser.add_argument("--skip", type=int, default=0, help="앞에서 건너뛸 장수")
    parser.add_argument("--item", type=str, default=None, help="특정 품목만")
    parser.add_argument("--no-vlm", action="store_true", help="YOLO까지만 측정 (무료)")
    args = parser.parse_args()

    rows = [r for r in load_rows() if (IMAGES_DIR / r["filename"].strip()).exists()]
    if args.item:
        rows = [r for r in rows if canonical_item(r["item"]) == canonical_item(args.item)]

    # Before/After 짝이 갈라지지 않도록 pair_id 단위로 먼저 묶은 뒤 자른다.
    # 짝의 Before만 잘려 나가면 6번 지표를 잴 수 없다.
    rows.sort(
        key=lambda r: (
            r.get("pair_id", "").strip() or r["filename"].strip(),
            0 if r["phase"].strip().lower() == "before" else 1,
        )
    )
    if args.skip:
        rows = rows[args.skip :]
    if args.limit:
        rows = rows[: args.limit]

    if not rows:
        print("처리할 사진이 없습니다. eval_frozen/images/ 를 확인하세요.")
        return 1

    use_vlm = not args.no_vlm
    total = len(rows)
    if use_vlm:
        print(f"{total}장 처리 — VLM 호출 {total}회, 예상 비용 약 ${total * 0.004:.2f}\n")
    else:
        print(f"{total}장 처리 — YOLO만 측정 (VLM 호출 없음)\n")

    metrics = Metrics()

    # Before → After 순서를 지켜야 비교가 성립한다. pair_id로 묶어 Before를 먼저 돌린다.
    order = sorted(
        rows,
        key=lambda r: (r.get("pair_id", "").strip(), 0 if r["phase"].strip().lower() == "before" else 1),
    )
    before_ids: dict[str, str] = {}

    header = f"{'파일':<26} {'품목':<14} {'판정':<14} {'결론':<8} {'상태':<8}"
    print(header)
    print("-" * 78)

    for row in order:
        name = row["filename"].strip()
        item = canonical_item(row["item"])
        pair_id = row.get("pair_id", "").strip()
        phase = row["phase"].strip().lower()

        yolo_only(row, metrics)

        if not use_vlm:
            print(f"{name:<26} {item:<14} {'(생략)':<14}")
            continue

        started = time.perf_counter()
        try:
            response = run_one(
                row,
                before_id=before_ids.get(pair_id) if phase == "after" else None,
                use_vlm=True,
            )
        except Exception as exc:  # 한 장 실패가 전체 측정을 멈추면 안 된다
            metrics.misses.append(f"{name}: 예외 {exc}")
            print(f"{name:<26} {item:<14} {'실패':<14} {str(exc)[:30]}")
            continue

        metrics.elapsed_ms.append(response.processing.elapsed_ms)
        if response.processing.used_vlm:
            metrics.vlm_calls += 1
        if response.processing.cache_hit:
            metrics.cache_hits += 1

        if phase == "before" and pair_id:
            before_ids[pair_id] = response.analysis_id

        # --- 3번: 품목 정확도 ---
        if item not in ITEM_TO_CLASS:
            metrics.unknown_items.add(row["item"].strip())
        got_item = response.detection.item_name_ko
        item_ok = got_item == item
        metrics.vlm_item.add(item_ok)

        # --- 4번: 상태 정확도 ---
        wanted = expected_states(row["state"])
        for key, want in wanted.items():
            got = response.states.get(key)
            if got is None:
                continue  # 그 품목 스키마에 없는 키는 채점하지 않는다
            metrics.vlm_state.add(got.value == want)

        # --- 5번: 최종 결론 정확도 ---
        conclusion_ok = judge_conclusion(row, response, metrics)
        metrics.conclusion.add(conclusion_ok)
        metrics.per_item[item].add(conclusion_ok)

        # --- 6번: Before/After 판정 ---
        if phase == "after":
            comp = response.comparison
            ba_ok = comp is not None and comp.same_class and bool(comp.improved_actions)
            metrics.before_after.add(ba_ok)

        if not conclusion_ok:
            if response.error is not None:
                got_disposal = f"{response.status} / {response.error.code}"
            elif response.disposal is not None:
                got_disposal = response.disposal.category_name_ko
            else:
                got_disposal = str(response.status)
            metrics.misses.append(
                f"{name} | 기대 '{row['expected'].strip()}' → 실제 '{got_disposal}' "
                f"(판정: {got_item})"
            )
            metrics.error_codes[str(response.error.code) if response.error else "오분류"] += 1

        mark = "O" if conclusion_ok else "X"
        # 거부·실패는 사유 코드까지 찍는다. 코드가 없으면 무엇을 고쳐야 할지
        # 알 수 없어 실패 목록이 그냥 '안 됨' 더미가 된다.
        reason = f" ({response.error.code})" if response.error else ""
        print(
            f"{name:<26} {item:<14} {str(got_item):<14} {mark:<4} "
            f"{str(response.status)}{reason}"
        )

    # ---------------------------------------------------------------- 요약
    print("\n" + "=" * 78)
    print("지시서 §7.3 지표")
    print("=" * 78)
    print(f"1. YOLO 검출률        : {metrics.detection}")
    print(f"2. YOLO 클래스 정확도  : {metrics.yolo_class}   (참고 지표)")
    if use_vlm:
        print(f"3. VLM 품목 정확도    : {metrics.vlm_item}")
        print(f"4. VLM 상태 정확도    : {metrics.vlm_state}")
        print(f"5. 최종 결론 정확도   : {metrics.conclusion}   <-- 가장 중요")
        print(f"6. Before/After 판정  : {metrics.before_after}")
        avg = sum(metrics.elapsed_ms) / len(metrics.elapsed_ms) if metrics.elapsed_ms else 0
        print(f"7. 평균 응답 시간     : {avg:.0f} ms/장")
        print(f"   VLM 호출 횟수      : {metrics.vlm_calls}")
        print(f"   캐시 히트율        : {metrics.cache_hits}/{len(metrics.elapsed_ms)} (STEP 9 전이므로 0)")

    if use_vlm and metrics.per_item:
        print("\n품목별 최종 결론 정확도")
        for item, counter in sorted(metrics.per_item.items(), key=lambda kv: kv[1].rate):
            print(f"  {item:<18} {counter}")

    if metrics.unknown_items:
        print("\nCSV item 이름이 도감에 없습니다. CSV 또는 ITEM_ALIASES 확인 필요")
        for value in sorted(metrics.unknown_items):
            print(f"  - {value}")

    if metrics.unmapped_expected:
        print("\nCSV expected 값을 배출 분류로 옮기지 못했습니다. 라벨 또는 매핑 확인 필요")
        for value in sorted(metrics.unmapped_expected):
            print(f"  - {value}")

    if metrics.misses:
        print(f"\n오답 {len(metrics.misses)}건")
        for miss in metrics.misses:
            print(f"  - {miss}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
