"""직접 찍은 사진으로 파이프라인을 돌려본다.

    python scripts/try_photo.py 사진.jpg
    python scripts/try_photo.py 사진들폴더/
    python scripts/try_photo.py before.jpg after.jpg --pair
    python scripts/try_photo.py 아이스팩.jpg --choice water

**여러 장을 채점하려면 폴더 이름을 도감 품목명으로 두고 `--check` 를 준다.**

    새사진/
      투명 페트병/  IMG_001.jpg  IMG_002.jpg
      알루미늄캔/    IMG_003.jpg
      택배상자/      IMG_004.jpg

    python scripts/try_photo.py 새사진/ --check

폴더 이름이 곧 정답이라 CSV를 만들 필요가 없다. 몇 장이 맞았고 무엇을
무엇으로 헷갈렸는지 표로 나온다.

평가 스크립트(`evaluate.py`)와 역할이 다르다. 저기는 **동결 평가셋**을 CSV 정답과
대조해 공식 성능 수치를 낸다. 여기는 **새로 찍은 사진**을 보는 곳이다.

`eval_frozen/` 은 성능 근거라 프롬프트를 고치며 반복해 쓰면 과적합이 된다.
프롬프트를 손보고 싶을 때는 반드시 여기를 쓴다. (지시서 §11-2)

사진은 스마트폰에서 나온 크기 그대로 넣으면 된다. 서버가 업로드와 같은
규격(긴 변 1024px)으로 줄인다.

⚠️ **프롬프트나 규칙을 고치고 다시 잴 때는 `--no-cache` 를 준다.** 캐시는 사진
내용으로 키를 잡으므로, 같은 사진이면 고치기 전 판정이 그대로 되돌아온다.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.schemas.enums import ITEM_TO_CLASS  # noqa: E402
from app.schemas.request import AnalyzeRequest  # noqa: E402
from app.schemas.response import AnalyzeResponse  # noqa: E402
from app.services import pipeline  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

#: 상태값을 사람 말로. 표에서 한눈에 읽히게 한다.
_STATE_KO = {
    "yes": "그렇다",
    "no": "아니다",
    "unknown": "모르겠다",
    "not_applicable": "해당 없음",
}


def collect(paths: list[str]) -> list[Path]:
    """사진을 모은다. 폴더는 하위 폴더까지 훑는다(`--check` 의 품목 폴더 때문)."""
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(
                sorted(f for f in p.rglob("*") if f.suffix.lower() in IMAGE_SUFFIXES)
            )
        elif p.exists():
            found.append(p)
        else:
            print(f"파일이 없습니다: {p}")
    return found


def expected_item(path: Path) -> str | None:
    """상위 폴더 이름이 도감 품목이면 그것이 정답이다."""
    name = path.parent.name.strip()
    return name if name in ITEM_TO_CLASS else None


def show(
    path: Path, response: AnalyzeResponse, elapsed: float, *, expected: str | None = None
) -> None:
    det = response.detection
    cached = " · 캐시" if response.processing.cache_hit else ""
    print(f"\n{'=' * 66}")
    print(f"{path.name}   ({elapsed:.1f}초{cached})")
    print("=" * 66)

    if response.error is not None:
        print(f"  결과      거부 — {response.error.code}")
        if expected:
            print(f"  정답      {expected}  → X (판정까지 가지 못함)")
        print(f"  아이에게  {response.feedback.title} / {response.feedback.message}")
        return

    if expected:
        mark = "O 맞음" if det.item_name_ko == expected else f"X 틀림 (정답: {expected})"
        print(f"  채점      {mark}")
    print(f"  무엇      {det.item_name_ko}  ({det.class_name_ko or '-'})")
    src = "YOLO 크롭" if det.source == "yolo" else "원본 전체 (검출 실패 → 폴백)"
    print(f"  경로      {src}" + (f", conf {det.confidence:.2f}" if det.confidence else ""))
    print(f"  상태값    {response.status}")

    if response.states:
        print("\n  지금 상태")
        for key, item in sorted(response.states.items()):
            value = _STATE_KO.get(str(item.value), str(item.value))
            print(f"      {key:<18} {value:<8} (확신 {item.confidence:.2f})")

    if response.required_actions:
        print("\n  남은 준비")
        for i, action in enumerate(response.required_actions, 1):
            print(f"      {i}. {action.label_ko}  [{action.code}]")
    else:
        print("\n  남은 준비   없음 — 배출해도 된다")

    if response.disposal is not None:
        print(f"\n  배출처    {response.disposal.category_name_ko}  ({response.disposal.rule_id})")

    if response.comparison is not None:
        c = response.comparison
        print("\n  Before와 비교")
        print(f"      해낸 것    {[a for a in c.improved_actions] or '없음'}")
        print(f"      남은 것    {[a for a in c.remaining_actions] or '없음'}")
        if c.regressed_actions:
            print(f"      되돌아감   {[a for a in c.regressed_actions]}")
        print(f"      보상 참고값 {response.reward_eligible}")

    print(f"\n  아이에게  {response.feedback.title}")
    print(f"            {response.feedback.message}")


def run(path: Path, *, phase: str, before_id: str | None, choice: str | None) -> AnalyzeResponse:
    req = AnalyzeRequest(
        scanSessionId=f"try_{path.stem}",
        phase=phase,
        beforeAnalysisId=before_id,
        userChoice=choice,
    )
    return pipeline.run(path.read_bytes(), req)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="사진 파일 또는 폴더")
    parser.add_argument("--phase", default="BEFORE", choices=["BEFORE", "AFTER", "SINGLE"])
    parser.add_argument(
        "--pair",
        action="store_true",
        help="사진 두 장을 Before/After 한 쌍으로 본다 (첫 장 → 둘째 장)",
    )
    parser.add_argument("--choice", default=None, help="사용자 선택 (아이스팩: gel|water)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="상위 폴더 이름을 정답으로 보고 채점한다 (폴더명 = 도감 품목명)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="캐시를 무시하고 매번 새로 판정한다 (프롬프트·규칙을 고친 뒤에 쓴다)",
    )
    args = parser.parse_args()

    if args.no_cache:
        # 캐시는 사진 내용으로 키를 잡는다. 프롬프트를 고쳐도 같은 사진이면
        # 고치기 전 판정이 그대로 나오므로, 재측정할 때는 꺼야 한다.
        os.environ["CACHE_ENABLED"] = "false"
        from app.core.config import get_settings  # noqa: PLC0415

        get_settings.cache_clear()
        print("캐시를 끄고 실행합니다 (매번 새로 판정).\n")

    images = collect(args.paths)
    if not images:
        print("처리할 사진이 없습니다.")
        return 1

    if args.pair:
        if len(images) != 2:
            print(f"--pair 는 사진 두 장이 필요하다 (지금 {len(images)}장)")
            return 1
        before_path, after_path = images

        started = time.perf_counter()
        before = run(before_path, phase="BEFORE", before_id=None, choice=args.choice)
        show(before_path, before, time.perf_counter() - started)

        if before.error is not None:
            print("\nBefore가 거부되어 비교할 수 없다. Before 사진부터 다시 찍는다.")
            return 1

        started = time.perf_counter()
        after = run(
            after_path, phase="AFTER", before_id=before.analysis_id, choice=args.choice
        )
        show(after_path, after, time.perf_counter() - started)
        return 0

    print(f"{len(images)}장 처리 — VLM 호출 {len(images)}회, 약 ${len(images) * 0.008:.2f}")

    if args.check:
        labelled = [p for p in images if expected_item(p)]
        if not labelled:
            print(
                "\n--check 를 줬는데 정답을 알 수 없습니다.\n"
                "사진을 도감 품목명 폴더에 넣어주세요. 예: 새사진/투명 페트병/IMG_1.jpg\n"
                f"쓸 수 있는 이름: {', '.join(sorted(ITEM_TO_CLASS))}"
            )
            return 1
        if len(labelled) < len(images):
            skipped = [p.name for p in images if not expected_item(p)]
            print(f"  (품목 폴더가 아니어서 채점 제외: {len(skipped)}장 — {skipped[:3]})")

    hit = total = 0
    confusion: dict[str, Counter] = defaultdict(Counter)
    rejected: Counter = Counter()

    for path in images:
        started = time.perf_counter()
        try:
            response = run(path, phase=args.phase, before_id=None, choice=args.choice)
        except Exception as exc:  # 한 장이 터져도 나머지는 계속 본다
            print(f"\n{path.name}: 실패 — {exc}")
            continue

        want = expected_item(path) if args.check else None
        show(path, response, time.perf_counter() - started, expected=want)

        if want:
            total += 1
            got = response.detection.item_name_ko
            if response.error is not None:
                rejected[str(response.error.code)] += 1
                confusion[want]["(거부됨)"] += 1
            else:
                hit += int(got == want)
                confusion[want][got or "(판정 실패)"] += 1

    if args.check and total:
        print(f"\n{'=' * 66}")
        print(f"채점 — 품목 정확도 {hit}/{total} = {hit / total:.1%}")
        print("=" * 66)
        for want in sorted(confusion):
            got_counts = confusion[want]
            right = got_counts.get(want, 0)
            n = sum(got_counts.values())
            print(f"\n  {want}  {right}/{n}")
            for got, count in got_counts.most_common():
                mark = "O" if got == want else "X"
                print(f"      {mark}  {got:<20} {count}장")
        if rejected:
            print("\n  거부된 사진")
            for code, count in rejected.most_common():
                print(f"      {code:<22} {count}장")
        print(
            "\n  X 가 많은 품목이 프롬프트를 손볼 곳이다.\n"
            "  고친 뒤에는 --no-cache 를 붙여 다시 잰다."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
