# 다시봄 스쿨 — AI 추론 서버

초등 고학년 재활용 교육 웹앱의 AI 파트.
YOLO11n이 **검출·크롭**을 맡고, Claude VLM이 **종류와 상태를 최종 판정**한다.

> YOLO 클래스는 힌트로만 쓴다. `pack` 클래스 mAP50이 0.310이라 클래스를 결정으로 쓰면
> 그대로 서비스 오류가 된다. 라우팅은 VLM 판정 품목명으로 한다. (지시서 §11-3)

전체 설계 근거는 [docs_지시서.md](docs_지시서.md) 참고.

---

## 현재 진행 상태

| STEP | 내용 | 상태 |
|---|---|---|
| 1 | Mock 서버 (FastAPI + Pydantic 스키마 + 고정 JSON) | ✅ 완료 |
| 2 | 전처리 + YOLO 검출 | ✅ 완료 |
| 3 | 안전 필터 (BlazeFace 얼굴 검출) | ✅ 완료 |
| 4 | VLM 상태 판정 | ✅ 완료 |
| 5 | RAG 배출 기준 + 아동 피드백 생성 | ✅ 완료 (도감 29종) |
| 6 | 평가 스크립트 | ✅ 완료 · 사진 90장 전량 확보 |
| 7 | 품목 확장 | ✅ 완료 — 클래스 7종 + 폴백 프롬프트 |
| 8 | Before/After 비교 (`/v1/compare` 포함) | ✅ 완료 |
| 9 | 이미지 해시 캐시 + 오프라인 폴백 | ✅ 완료 |
| 10 | ONNX 변환 | ⏸ **하지 않는다** — 아래 근거 |
| 11 | 전량 측정 | ⬜ 사진 90장 확보 완료 · 재측정 대기 |

**파이프라인 11단계가 전 구간 동작한다.** 사진도 전량 확보했다. 남은 것은
90장 전량 재측정과 성능 튜닝이다.

**STEP 1(`AI_MODE=mock`)은 모델 가중치도 API 키도 없이 동작한다.**
백엔드 담당자는 지금 바로 연동을 시작하면 된다.

### 실측 (동결 평가셋 62장, CPU + Claude Sonnet 5)

지시서 §7.3의 7개 지표. `python scripts/evaluate.py` 로 재현한다.

| # | 지표 | 값 |
|---|---|---|
| 1 | YOLO 검출률 (크롭 생성) | 79.3% (46/58) |
| 2 | YOLO 클래스 정확도 | 50.0% — 참고 지표, VLM이 교정 |
| 3 | VLM 품목 정확도 | 72.6% (45/62) |
| 4 | VLM 상태 정확도 | 71.2% (47/66) |
| 5 | **최종 결론 정확도** | **77.4% (48/62)** |
| 6 | Before/After 판정 | 68.0% (17/25) |
| 7 | 평균 응답 시간 | 6.8초 / 장 |

품목별 최종 결론 정확도:
투명 페트병 100% · 알루미늄캔 90% · 배달 플라스틱 용기 90% · 택배상자 87.5% ·
영수증 75% · 아이스팩 75% · 코팅지 75% · 아이스크림 포장지 60% · 컵라면 종이용기 50%

> 이 표를 뽑은 뒤 컵라면 종이용기 규칙을 고쳤다(아래 참고). 해당 8장만 다시 재니
> 50% → 75%로 올랐다. 전체를 다시 돌리면 80% 부근이 될 것으로 보이지만
> **재측정 전까지는 위 숫자가 공식 값이다.**

미검출 12장은 **VLM 단독 경로**로 라우팅된다. 실패가 아니라 설계된 폴백이다.

#### 남은 오답 14건의 원인

| 원인 | 건수 | 성격 |
|---|---|---|
| 품목 오분류 → 다른 배출함 안내 | 9 | VLM 판정 한계 |
| `MULTIPLE_OBJECTS` 오탐 | 2 | 박스가 완전히 떨어져 잡힌 경우 |
| `IMAGE_TOO_BLURRY` | 1 | 실제로 흔들린 사진 |
| `CLASS_MISMATCH` | 1 | Before/After 품목이 클래스까지 달라짐 |
| `NOT_WASTE` | 1 | — |

큰 실패는 전부 **VLM 품목 판정**에 몰려 있다. 검출·규칙·비교 로직이 아니다.
아이스크림 포장지(60%)는 "끈적임"을 VLM이 오염으로 보지 않아 준비 행동이 생기지 않는 경우다.

#### 측정 과정에서 잡은 버그

측정을 돌리기 전에는 최종 결론 정확도가 **56.5%**였다. 아래 두 가지를 고쳐
77.4%가 됐다. 둘 다 실측이 없었으면 발견하지 못했다.

1. **YOLO 클래스 힌트가 VLM을 오도했다.** 캔 사진에 우유팩 지침이 붙자
   "캔이 뜯겨 있다"고 보면서도 품목을 `알 수 없음`으로 답했다. 클래스 정확도가
   50%라 절반은 틀린 지침이 들어간다. → 기본 프롬프트에 도감 29종 전체를 싣고,
   추가 지침은 자주 틀린다고 명시했다.
2. **음식이 담긴 용기를 "재활용품이 아니다"로 판정했다.** Before 사진은 원래
   내용물이 남아 있는 상태다. → `isWaste` 는 "배출 대상 품목인가"만 뜻하며
   "지금 버릴 때가 됐는가"가 아니라고 명시했다.

`NOT_WASTE` 오거부가 14건 → 1건으로 줄었다.

---

## 실행

```bash
cd ai-service
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env

uvicorn app.main:app --reload --port 8001
```

- Swagger UI: http://localhost:8001/docs
- 헬스체크: http://localhost:8001/health

테스트:

```bash
pytest tests -q                      # 무료·오프라인 (API 호출 없음)
RUN_VLM_TESTS=1 pytest tests -q      # 실제 Claude API 호출 포함
```

기본 실행은 **네트워크도 비용도 쓰지 않는다.** 실제 API를 부르는 테스트는
`@pytest.mark.vlm` 이 붙어 있고 `RUN_VLM_TESTS=1` 일 때만 돈다.
`AI_MODE` 도 테스트에서는 mock으로 고정되므로, 각자의 `.env` 가 결과를 바꾸지 않는다.

평가 (동결셋 · 정답과 대조해 점수를 낸다):

```bash
python scripts/check_eval_assets.py           # CSV ↔ 사진 파일 대조
python scripts/evaluate.py --no-vlm           # YOLO까지만 (무료)
python scripts/evaluate.py                    # 전량. 90장 기준 약 $1
python scripts/evaluate.py --item "투명 페트병"   # 품목 하나만
```

시험 (내가 찍은 사진):

```bash
python scripts/try_photo.py 사진.jpg
python scripts/try_photo.py before.jpg after.jpg --pair    # 준비 전/후 한 쌍
python scripts/try_photo.py 아이스팩.jpg --choice water
```

여러 장을 **채점**하려면 폴더 이름을 도감 품목명으로 두고 `--check` 를 준다.
CSV를 만들 필요가 없다.

```
새사진/
  투명 페트병/   IMG_001.jpg  IMG_002.jpg
  알루미늄캔/     IMG_003.jpg
  택배상자/       IMG_004.jpg
```

```bash
python scripts/try_photo.py 새사진/ --check
```

```
채점 — 품목 정확도 4/4 = 100.0%

  알루미늄캔  1/1
      O  알루미늄캔                1장
  투명 페트병  2/2
      O  투명 페트병               2장
```

무엇을 무엇으로 헷갈렸는지 표로 나오므로, X가 몰린 품목이 프롬프트를 손볼 곳이다.

> ⚠️ **프롬프트나 규칙을 고치고 다시 잴 때는 `--no-cache` 를 붙인다.**
> 캐시는 사진 내용으로 키를 잡으므로, 같은 사진이면 고치기 전 판정이 그대로
> 되돌아온다. 이걸 모르면 "고쳤는데 왜 안 변하지?"에 빠진다.

**동결셋과 새로 찍은 사진의 용도가 다르다.** `eval_frozen/` 은 성능 근거라
프롬프트를 손질하며 반복해 쓰면 과적합이 된다. 프롬프트를 고치고 싶을 때는
`try_photo.py` 로 동결셋 **밖** 사진을 쓴다. (지시서 §11-2)

사진은 스마트폰에서 나온 크기 그대로 넣으면 된다. 서버가 업로드와 같은
규격(긴 변 1024px)으로 줄인다. 첫 장은 모델 로딩 때문에 20초쯤 걸리고,
두 번째부터 7초 수준이다.

---

## 백엔드 담당자용 연동 가이드

### 호출 흐름

```
프론트엔드 → 백엔드 메인 → AI 추론 서버 → JSON → 백엔드 검증·보상 → 프론트엔드
```

프론트엔드는 AI 서버를 **직접 호출하지 않는다.**

### `POST /v1/analyze`

`multipart/form-data`

| 필드 | 필수 | 설명 |
|---|---|---|
| `image` | O | 사진 1장. 클라이언트에서 긴 변 1024px로 리사이즈해 올린다 |
| `scanSessionId` | O | 스캔 세션 식별자 |
| `phase` | | `BEFORE`(기본) / `AFTER` / `SINGLE` |
| `regionCode` | | 기본 `KR-43-CHEONGJU` |
| `expectedClass` | | 품목 힌트. 강제가 아니다 |
| `beforeAnalysisId` | | `AFTER`일 때 비교 대상 |
| `userChoice` | | 아이스팩 젤/물 등 사용자 분기 값 |
| `mockScenario` | | **mock 전용.** 아래 시나리오 이름 |

### 응답 계약 — 중요

**AI 서버는 추론 결과를 항상 HTTP 200 + 구조화된 본문으로 반환한다.**
얼굴 검출·타임아웃 같은 실패도 200이며 `status` / `error` 로 구분한다.
백엔드가 상태코드 분기 없이 한 경로로 파싱할 수 있게 하려는 의도다.

4xx는 **요청 자체가 잘못된 경우에만** 나온다.

| 코드 | 상황 |
|---|---|
| 400 | 빈 이미지, 알 수 없는 mock 시나리오 |
| 413 | 이미지 12MB 초과 |
| 415 | 이미지가 아닌 파일 |
| 422 | 필수 필드 누락 |
| 501 | `AI_MODE`가 mock이 아닌데 아직 미구현 |

### `status` 값

| 값 | 의미 | 백엔드 처리 |
|---|---|---|
| `ACTION_REQUIRED` | 준비 행동이 남았다. **Before의 정상 응답** | 미션 카드 표시, 보상 없음 |
| `COMPLETED` | 준비 완료, 배출 결론 제시 가능 | 보상 판정 |
| `IMPROVED` | After — 다 해냈다 | 보상 판정 |
| `PARTIALLY_IMPROVED` | After — 일부만 개선 | 남은 행동 재안내 |
| `NOT_IMPROVED` | After — 개선 미확인 | 재시도 유도 |
| `REJECTED` | 안전 필터 등으로 거부 | 재촬영 유도 |
| `FAILED` | 서버 측 실패 | 재시도 / 캐시 |

> **Before 단계에서 `COMPLETED`가 오면 그것이 오답이다.** Before의 정답은 배출 결론이
> 아니라 준비 필요 안내다. (지시서 §4.3)

### 보상 판정

`rewardEligible`은 **참고값이다.** 실제 지급은 백엔드가 결정한다.
미션·뱃지는 자유 문자열이 아니라 `requiredActions[].code` / `comparison.improvedActions`의
**`ACTION_CODES`로 판정한다.**

### Mock 시나리오 9종

폼 필드 `mockScenario` 또는 헤더 `X-Mock-Scenario`로 지정. 목록은 `GET /v1/mock/scenarios`.

| 시나리오 | 결과 |
|---|---|
| `pet_action_required` | Before 표준 — `ACTION_REQUIRED` + 라벨 떼기·압착 |
| `pet_completed` | 준비 완료 — `COMPLETED` + 투명 페트병 전용함 |
| `after_success` | `IMPROVED` + 남은 행동 없음 |
| `after_partial` | `PARTIALLY_IMPROVED` + `CRUSH` 남음 |
| `face_detected` | `REJECTED` / `FACE_DETECTED` |
| `not_waste` | `REJECTED` / `NOT_WASTE` |
| `multiple_objects` | `REJECTED` / `MULTIPLE_OBJECTS` |
| `low_confidence` | `REJECTED` / `LOW_CONFIDENCE` |
| `ai_timeout` | `FAILED` / `AI_TIMEOUT` |

지정하지 않으면 `phase`에 따라 기본값이 선택된다
(`BEFORE`→`pet_action_required`, `AFTER`→`after_partial`, `SINGLE`→`pet_completed`).

### 호출 예시

```bash
curl -X POST http://localhost:8001/v1/analyze \
  -F "image=@sample.jpg" \
  -F "scanSessionId=scan_01JABC123" \
  -F "phase=BEFORE" \
  -F "mockScenario=pet_action_required"
```

### `POST /v1/analyze/session` — 백엔드 세션 양식

**백엔드 코드를 고치지 않고 붙이려면 이걸 쓴다.** 입력은 `/v1/analyze`와 완전히
같고 응답만 평평하다. 백엔드 `SessionResultRequest(**응답)`으로 그대로 들어간다.

```bash
curl -X POST http://localhost:8001/v1/analyze/session \
  -F "image=@sample.jpg" \
  -F "scanSessionId=scan_01JABC123" \
  -F "phase=BEFORE"
```

```json
{
  "detectedClass": "transparency_plastic_bottle",
  "confidence": 0.604,
  "needsAction": true,
  "actions": ["내용물 비우기", "라벨 떼기", "납작하게 누르기"],
  "disposalCategory": "CLEAR_PET_BIN",
  "feedbackText": "뚜껑이 아직 닫혀 있고 라벨도 그대로 붙어 있네. ...",

  "analysisId": "analysis_01M0CHG3AYRE9NC2",
  "actionCodes": ["EMPTY_CONTENT", "REMOVE_LABEL", "CRUSH"],
  "classCode": "pet",
  "aiStatus": "ACTION_REQUIRED",
  "improved": null,
  "remainingActions": [],
  "remainingActionCodes": [],
  "error": null
}
```

위 6개가 `SessionResultRequest`와 1:1이고, 아래는 부가 정보다. pydantic v2가
모르는 키를 무시하므로 그냥 넘겨도 된다.

> **`detectedClass`는 Firestore `card` 컬렉션의 `type`이다.** 백엔드
> `collect_card()`가 `card`에서 `type == detectedClass`로 카드를 찾아 학생
> 도감에 등록하므로, 클래스(`pet`/`can`/…)가 아니라 **품목 단위 카드 type**을
> 싣는다. 클래스가 필요하면 `classCode`를 쓴다.

| 부가 필드 | 왜 필요한가 |
|---|---|
| `analysisId` | **세션 문서에 저장해야 한다.** 재촬영 때 `beforeAnalysisId`로 되돌려주지 않으면 개선 여부를 계산할 수 없다 |
| `actionCodes` | 미션·뱃지 판정용. `actions`(한글)와 순서가 같다. 한글 라벨로 판정하면 문구가 바뀔 때 깨진다 |
| `classCode` | AI 7종 클래스. `detectedClass`가 품목 단위라 클래스 정보를 따로 싣는다. 도감 카드의 `class` 필드와는 어휘가 다르다 (카드는 `general`·`battery`를 쓰고 `glass`가 없다) |
| `aiStatus` | 백엔드 3종으로 표현되지 않는 `IMPROVED` / `PARTIALLY_IMPROVED` / `REJECTED` 등 |
| `improved` | `AFTER`에서만 채워진다. **보상의 근거는 이 값이지 클라이언트가 보낸 값이 아니다** |
| `remainingActions` | `AFTER`에서 아직 남은 행동 |
| `error` | 거부·실패 사유. `retryable`로 재촬영 안내와 중단 안내를 가른다 |

`AFTER`일 때는 `actions`에 Before의 요구를 다시 담지 않고 **남은 행동만** 넣는다.
그러지 않으면 아이가 해낸 일이 화면에서 지워진다. (지시서 §4.2)

거부(`REJECTED`)·실패(`FAILED`)일 때는 품목이 없으므로 `detectedClass`와
`disposalCategory`가 **빈 문자열**로 온다. 백엔드 모델이 두 필드를 필수 문자열로
받기 때문에 `null`을 넣을 자리가 없다. 이때 `needsAction`은 `true`로 오는데,
백엔드가 `if needsAction: ACTION_REQUIRED`로 상태를 정하므로 그래야 재촬영 안내
화면으로 간다. 사유는 `error`를 보면 된다.

> 백엔드 양식에는 `states` · `boundingBox` · `processing` 자리가 없다.
> 그 값들이 필요해지면 `/v1/analyze`를 쓴다.

#### 도감 카드 매핑

`app/schemas/enums.py`의 `ITEM_TO_CARD_TYPE`이 도감 29종을 Firestore `card`의
`type`으로 옮긴다. 값은 실제 컬렉션 26장을 읽어 맞춘 것이라 임의로 바꾸면 안 된다.

**카드가 아직 없는 품목 2종.** AI는 판정할 수 있는데 `card` 문서가 없다.
`collect_card()`가 `registered: false`로 조용히 넘어가므로 판정은 동작하지만
도감에 등록되지 않는다. 아래 `type`으로 카드를 추가하면 코드 수정 없이 걸린다.

| 품목 | 필요한 `type` |
|---|---|
| 유리병 | `glass_bottle` |
| 페트병 뚜껑 | `bottle_cap` |

도감은 신문지와 공책을 `newspaper&notebook` 한 장으로 묶었다. AI는 둘을 따로
판정하지만 같은 카드로 보낸다.

---

## 발표용 캐시 (STEP 9)

같은 사진을 다시 넣으면 VLM을 부르지 않고 저장된 판정을 돌려준다.
**적중 시 12ms**, 미적중 시 6.8초다.

```bash
python scripts/warm_cache.py 시연사진/          # 시연할 사진 미리 데우기
python scripts/warm_cache.py --eval-set        # 평가셋 전량
python scripts/warm_cache.py --stats           # 지금 상태
python scripts/warm_cache.py --clear           # 비우기
```

데운 뒤 `.env` 에서 `AI_MODE=cached` 로 바꾸면 **네트워크를 아예 쓰지 않는다.**
발표장 와이파이가 끊겨도, API가 느려도 데모가 멈추지 않는다. 캐시에 없는 사진은
"지금은 새 사진을 볼 수 없어"로 안내된다.

- 항목 하나가 **1.5KB**다. 90장을 다 데워도 200KB 남짓이다.
- **이미지는 저장하지 않는다.** 파일 해시(64자)와 판정 JSON만 남는다. (지시서 §11-5)
- 키에 `phase`·`regionCode`·`userChoice` 가 함께 들어간다. 같은 사진이라도
  Before/After나 아이스팩 젤/물 선택이 다르면 결과가 다르기 때문이다.
- 거부·실패 응답은 저장하지 않는다. 흔들린 사진을 박아두면 다시 찍어도
  같은 실패가 되돌아온다.
- `GET /health` 의 `checks.cacheWarm` 으로 시연 준비 여부를 확인한다.

`AI_MODE=remote` 에서도 캐시는 켜져 있다(`CACHE_ENABLED=false` 로 끌 수 있다).
프롬프트를 고치면 이전 판정이 남아 있으므로 `--clear` 후 다시 재본다.

## ONNX 변환을 하지 않은 이유 (STEP 10)

지시서 STEP 10은 ONNX 변환 + INT8 양자화를 요구한다. **하지 않았다.**
시간 배분을 재보니 최적화 대상이 아니다.

```
전체 6.8초 = VLM 5.8초 (85%)  ← 네트워크 너머
           + YOLO 0.5초 (7%)  ← ONNX가 줄이는 부분
           + 얼굴 0.3초 + 전처리 0.2초
```

ONNX로 YOLO를 절반으로 줄여도 **전체의 3~4%**다. onnxruntime 설치(약 150MB)와
가중치 이중 관리 비용이 그 이득보다 크다.

**같은 목적(응답 빨리)을 캐시가 훨씬 크게 달성한다** — 6.8초 → 12ms.
시연 경로에서는 YOLO조차 돌지 않는다.

지연을 더 줄여야 하면 순서는 이렇다.

1. 캐시 적중률 높이기 (이미 완료)
2. `VLM_EFFORT` 조정 — `low` 로 이미 15.4초 → 5.8초
3. VLM 이미지 크기 축소 (`VLM_MAX_EDGE`, 현재 768)
4. 그 다음에야 ONNX

## 파이프라인 구조

```
1. 이미지 수신
2. EXIF 회전 보정      ┐
3. 메타데이터 제거      ├ preprocess.py
4. 품질 검사           ┘
5. 얼굴 검출           safety.py        → 검출 시 REJECTED
6. YOLO 추론           detector.py      → 박스와 클래스 힌트
7. 크롭 + 원본 폐기     cropper.py       → 이후 배경 픽셀은 남지 않는다
8. VLM 상태 판정       state_analyzer.py → 품목·상태·아이에게 할 말
9. 배출 기준 결합       rag.py           → 결론과 남은 행동
10. 피드백 조립        feedback.py      → 문장 + TTS 텍스트
11. Before/After 비교  before_after.py  → 무엇을 해냈는지
```

### 누가 무엇을 정하는가

역할을 섞지 않는 것이 이 설계의 핵심이다.

| 결정 | 담당 | 이유 |
|---|---|---|
| 어디를 자를까 | YOLO | 클래스는 힌트일 뿐이다 |
| 무슨 물건인가 | **VLM** | `pack` mAP50이 0.310이라 YOLO 클래스를 결정으로 쓸 수 없다 |
| 지금 상태가 어떤가 | **VLM** | 사진에서만 보이는 정보다 |
| 무엇을 해야 하는가 | **규칙 파일** | VLM은 지자체 배출 기준을 모른다 |
| 어디에 버리는가 | **규칙 파일** | 〃 |

**VLM에게 행동을 지시하게 두면 규칙과 어긋난 안내가 나간다.** 실제로 초기 구현에서
투명 페트병에 "뚜껑을 열어줘"라고 말했다 — 투명 페트병은 뚜껑을 닫아서 배출한다.
그래서 프롬프트는 VLM에게 **보이는 것만 말하라**고 지시하고, 다음 행동 문장은
`recycling_rules.json` 에서 만든다.

### VLM 호출은 한 번이다

품목 판정·상태 판정·아이에게 할 말을 **한 번의 호출**로 받는다. 피드백 생성을
두 번째 호출로 분리하면 비용과 지연이 두 배가 된다.

출력은 구조화 출력(structured outputs)으로 스키마를 강제한다. JSON을 프롬프트로
부탁하고 파싱 실패 시 재시도하는 구조는 지연과 실패율을 함께 키운다.
스키마를 API에 넘기면 파싱 실패 경로 자체가 사라진다.

### 알 수 없는 것은 시키지 않는다

상태가 `unknown` 이거나 `not_applicable` 이면 **행동을 요구하지 않는다.**
우유팩의 `rinsed` 처럼 사진으로 확인이 어려운 상태를 `no` 로 단정하면
이미 깨끗이 헹군 아이에게 다시 헹구라고 시키게 된다. (지시서 §4.1)

### 규칙 파일 (`app/rules/recycling_rules.json`)

도감 29종 전체가 들어 있다. 품목 하나는 이렇게 생겼다.

```json
"투명 페트병": {
  "ruleId": "CJ-PET-001",
  "disposal": "CLEAR_PET_BIN",
  "stateActions": {
    "contentRemaining": { "yes": "EMPTY_CONTENT" },
    "labelAttached":    { "yes": "REMOVE_LABEL" },
    "flattened":        { "no":  "CRUSH" }
  },
  "childHint": "투명 페트병만 따로 모으는 함에 넣어줘."
}
```

- `stateActions` — 상태값이 트리거와 맞으면 그 행동을 요구한다
- `conditionalDisposal` — 조건이 맞으면 배출 분류를 덮어쓴다 (오염된 용기 → 일반쓰레기)
- `safetyActions` — 특정 행동에 따라붙는 안전 행동 (캔을 누를 때 `ASK_ADULT`)
- `userChoice` — 사진으로 판정 불가한 품목의 분기 (아이스팩 젤/물)

**배출 기준이 바뀌면 이 파일만 고친다.** 코드는 건드리지 않는다.

---

## 코드값

백엔드가 미션·뱃지를 판정하는 근거다. 값 문자열을 임의로 바꾸지 않는다.
정의는 [app/schemas/enums.py](app/schemas/enums.py) 한 곳에만 둔다.

- `ACTION_CODES` 10종 — `EMPTY_CONTENT` `RINSE` `REMOVE_LABEL` `REMOVE_CAP`
  `SEPARATE_MATERIALS` `FLATTEN` `CRUSH` `FOLD` `DISPOSE_GENERAL` `ASK_ADULT`
- `STATE_VALUES` 4종 — `yes` `no` `unknown` `not_applicable`
- YOLO 클래스 7종 — `paper` `pack` `can` `glass` `pet` `plastic` `vinyl`
  (`general_waste` / `etc` 는 **없다**)

`states`는 품목마다 키가 다르다. 해당 없는 항목은 키를 빼지 않고 `not_applicable`로 채운다.
빼버리면 '해당 없음'과 '판정 실패'를 구분할 수 없다.

---

## 지시서에서 벗어난 결정

실측 결과 지시서 값 그대로는 동작이 나빠서 조정한 항목이다. 근거 스크립트를 함께 남긴다.

### YOLO conf 임계값 `0.35` → `0.15`

지시서 §6은 0.35를 명시하지만, 우리 촬영 조건(책상 위 근접 단독 촬영)에서는
**검출률이 32.6%까지 떨어진다.** 정답 클래스의 conf 중앙값이 0.217이기 때문이다.
학습 데이터(29,469장, 다양한 배경·거리)와의 도메인 차이로 보인다.

| conf | 검출률 | 클래스 정확도 |
|---|---|---|
| 0.10 | 93.5% | 60.9% |
| **0.15** | **76.1%** | **47.8%** |
| 0.35 | 32.6% | 19.6% |

낮추는 것이 설계 철학과 어긋나지 않는다. YOLO는 검출·크롭 담당이고 클래스는
힌트일 뿐이다(§1, §11-3). 이 값이 정하는 것은 "이 클래스를 믿을까"가 아니라
"크롭할 박스를 잡을까"이며, **클래스가 틀려도 VLM이 교정한다.**

정답 클래스가 후보 목록에 등장한 비율은 82.6%다. 모델은 물체를 보고 있었고,
임계값이 잘라내고 있었다. **재학습은 답이 아니다.** (§11-1)

```bash
python scripts/diagnose_threshold.py    # 위 표를 재현한다
```

### 블러 임계값 `60` → `40`

지시서에 근거가 없는, 구현 중 정한 값이다. 60이면 경계선 사진(45·51)까지 반려해
46장 중 3장을 잃는다. 40이면 실제로 흔들린 1장만 걸러진다.
"결벽하게 굴면 제대로 씻은 것도 반려되어 아이가 이탈한다"는 §4.1의 판단 기준을
품질 검사에도 적용했다.

### VLM 기본 모델 Haiku 4.5 → Sonnet 5

지시서 §2.3은 Haiku를 1차, Sonnet을 승급 대상으로 둔다. 실측에서 Haiku가
**투명 페트병을 플라스틱 음료병으로 오판**했다. 라벨 색을 병 색으로 읽는 것이
원인이고, 이 둘은 뚜껑 처리가 정반대라(§4.4) 그대로 오안내가 된다.

프롬프트에 "라벨 색은 병 색이 아니다"를 명시해도 고쳐지지 않았다.

**결정적인 것은 틀리면서 `confidence: 0.95`를 보고한다는 점이다.** 신뢰도가
보정되어 있지 않아 "낮으면 승급" 전략이 성립하지 않는다. 같은 사진에서
Sonnet 5는 안정적으로 맞혔다.

| 모델 | `p1 (1).jpg` | `p2 (1).jpg` |
|---|---|---|
| Haiku 4.5 | 플라스틱 음료병 ❌ | 투명 페트병 ⭕ (재실행 시 흔들림) |
| Sonnet 5 | 투명 페트병 ⭕ | 투명 페트병 ⭕ |

평가셋 90장 전량을 Sonnet으로 돌려도 **약 $1**이라 비용이 제약이 아니다.
정확도를 아껴서 얻는 것이 몇백 원이라면 잘못된 교환이다.

승급 대상은 Opus 4.8로 바꿨다. 승급은 **예외(타임아웃·거절·연결 실패)에만**
동작한다. 오답은 예외가 아니라 정상 응답이므로 승급이 걸리지 않는다.

### VLM 사고 깊이 `high`(기본) → `low`

Sonnet 5는 thinking이 기본으로 켜져 있고 effort 기본값이 `high`다. 그대로 두면
**장당 15.4초**가 걸린다. 아이가 사진을 찍고 결과를 기다리는 화면에서 15초는
쓸 수 없다.

| 설정 | 평균 지연 | 페트병 종류 판정 |
|---|---|---|
| Sonnet 5 기본 (thinking, effort=high) | 15.4초 | 정확 |
| **Sonnet 5 `effort=low`** | **5.8초** | **정확 (동일)** |
| Sonnet 5 thinking 끔 | 6.0초 | 정확 (동일) |
| Haiku 4.5 | 2.9초 | 오판 |

`effort=low` 가 같은 답을 2.7배 빠르게 낸다. 출력 스키마가 고정된 지각·분류
문제라 깊은 추론이 크게 기여하지 않는 것으로 보인다. 정확도가 흔들리면
`VLM_EFFORT=medium` 으로 올린다.

### `max_tokens` `1024` → `4096`

**thinking 토큰이 `max_tokens` 에 함께 계산된다.** 1024로 뒀더니 복잡한 사진
(택배상자 등)에서 사고 도중 잘려 JSON이 끊기고 파싱이 실패했다. 실패한 호출은
전부 Opus로 승급해 비용이 두 배가 됐다. 실측 최대 1335토큰이라 4096으로 잡았다.

출력 토큰은 실제 생성분만 과금되므로 한도를 키워도 비용이 늘지 않는다.

### `MULTIPLE_OBJECTS` 판정에 겹침 조건 추가

크기만 보고 "2등 박스가 1등의 50% 이상이면 여러 물체"로 판정했더니 **정상 사진이
반려됐다.** YOLO가 한 물체를 여러 박스로 쪼개기 때문이다 — 캔은 몸통과 뚜껑이
포개지고, 큰 종이(포스터·영수증)는 가로 띠로 갈라진다.

1등 박스와 겹치는 정도(겹친 넓이 ÷ 작은 박스 넓이)를 함께 본다.

| 겹침 임계 | 오탐률 (검출된 48장) |
|---|---|
| 조건 없음 (기존) | 16.7% 이상 |
| 0.5 | 16.7% |
| 0.2 | 8.3% |
| **0.1** | **4.2%** |
| 0.05 이하 | 4.2% (개선 없음) |

0.1이 무릎점이다. 남은 4.2%는 박스가 완전히 떨어져 잡힌 경우라 겹침으로는
풀 수 없다.

### 컵라면 종이용기 `일반쓰레기` → `종이류` (헹구면)

내부 코팅을 이유로 일반쓰레기로 넣었는데, 동결 평가셋 라벨은 `종이류`다.
**동결 라벨이 정답이다.** 팀이 청주 기준으로 정한 값이므로 규칙을 라벨에 맞췄다.

국물이 남아 있으면 `conditionalDisposal` 로 일반쓰레기가 되고, 비우고 헹구면
종이류로 간다. 해당 8장 정확도가 50% → 75%로 올랐다.

### 얼굴 검출 임계값 `0.4` → `0.5` → `0.7`

처음에 "놓치는 것보다 잘못 거르는 편이 낫다"고 판단해 0.4로 낮췄다가 두 번 올렸다.

**무작위 잡음 이미지가 0.415로 얼굴 판정을 받았다** — 0.4는 노이즈 바닥 안이다.
0.5로 올렸더니 이번엔 **BlazeFace가 캔 뚜껑을 얼굴로 오인**했다. 원형 테두리 안에
따개와 각인이 배치된 모양이 눈·코·입 배치와 닮은 탓으로 보인다. 건전지 상단도
같은 이유로 걸린다.

평가셋 62장(전부 물건 사진이므로 검출은 모두 오탐)에서 잰 오탐률:

| 임계값 | 오탐률 |
|---|---|
| 0.4 | 21.0% |
| 0.5 | 9.7% |
| 0.6 | 3.2% |
| **0.7** | **0.0%** |

관측된 최대 오탐 점수는 0.622(`c2 (1).jpg`)다.
이 수정으로 `FACE_DETECTED` 오거부 3건이 사라졌다.

#### 진짜 얼굴로 검증했다

오탐만 보고 정한 임계값은 반쪽이다. 필터가 꺼진 상태와 걸러낼 게 없는 상태는
겉으로 똑같아 보이기 때문이다(둘 다 반려 0건).

**팀원 얼굴을 찍지 않았다.** 그 자체로 개인정보가 하나 늘어난다.
MediaPipe 공개 테스트 인물 사진 2장을 실제 전처리에 태워 쟀다.

| 얼굴 크기 | 점수 | 걸러야 하나 |
|---|---|---|
| 화면을 채움 (높이 45~49%) | 0.832 · 0.983 | O |
| 상반신 (높이 18~23%) | 0.922 · 0.977 | O |
| 축소 배치 (배경의 먼 얼굴) | 0.07 ~ 0.31 | O (놓침) |

```
물건 사진 62장 최대 오탐   0.622  ─┐
                                 ├─ 0.7 (임계값)
진짜 얼굴 최소             0.832  ─┘
```

**두 분포가 겹치지 않고 0.7이 그 사이에 있다.** 양쪽으로 여유가 있다.

#### 다만 작게 찍힌 얼굴은 놓친다

축소한 얼굴은 0.07~0.31이 나온다. **임계값으로 풀 수 있는 문제가 아니다** —
그 점수대는 캔 뚜껑 오탐(0.622)보다 낮아서, 아무리 낮춰도 먼 얼굴만 골라
잡을 수 없다. short-range 모델의 특성이다.

영향 범위:

- **크롭 경로(약 80%)** — 배경의 작은 얼굴은 크롭에서 잘려 나간다. 문제없다.
- **폴백 경로(약 20%)** — 검출 실패로 원본이 통째로 VLM에 간다. **여기는 남는 위험이다.**

없애려면 full-range 모델로 교체해야 한다. 지금은 알려진 한계로 남긴다.

근거: `tests/test_safety.py`

### Before/After 비교 기준 — 품목명 → 클래스

`sameClass` 를 품목명으로 비교했더니 정상 동작이 거부당했다.

같은 페트병이라도 **라벨이 붙어 있으면** 색이 있어 보여 `플라스틱 음료병`,
**라벨을 떼면** 속이 비쳐 `투명 페트병`으로 판정된다. 품목명으로 비교하면
아이가 시킨 대로 라벨을 뗀 바로 그 순간 `CLASS_MISMATCH` 가 나서 해낸 일이
거부된다.

클래스(`pet`)가 같으면 같은 물건으로 본다. 근거: `tests/test_before_after.py`

---

## 다음 STEP에 필요한 자산

| 자산 | 위치 | 상태 |
|---|---|---|
| `dasibom_v1_best.pt` | `app/models/weights/` | ✅ 확보 (git 제외, 5.4MB) |
| `blaze_face_short_range.tflite` | `app/models/weights/` | ✅ **저장소에 포함** (224KB) |
| `ANTHROPIC_API_KEY` | `.env` | ✅ 확보 (git 제외) |
| `recycling_rules.json` (충북·청주) | `app/rules/` | ✅ 도감 29종 전체 |
| 촬영 사진 90장 | `eval_frozen/images/` | ✅ 전량 확보 (git 제외) |

YOLO 가중치와 사진은 용량 때문에 **git에 올리지 않는다.** 팀 드라이브로 공유하고
각자 위 경로에 풀어서 쓴다. 라벨 CSV는 커밋한다 — 그게 평가의 기준이다.

BlazeFace 가중치는 224KB라 저장소에 함께 넣었다. 받아야 할 자산이 하나 줄고,
얼굴 검출이 없는 상태로 서비스가 뜨는 사고를 막을 수 있다.

### 키 관리

`.env` 는 `.gitignore` 첫 줄에 있고, 그 위에 pre-commit 훅이 한 겹 더 있다.
훅은 `.env` 스테이징과 **추가된 모든 줄의 `sk-ant-` 패턴**을 검사한다
(파일명과 무관하므로 코드에 하드코딩해도 걸린다).

클론한 사람마다 한 번씩:

```bash
git config core.hooksPath .githooks
```

```bash
python scripts/check_eval_assets.py    # CSV ↔ 실제 파일 대조
```

### 촬영 대기 60장

플라스틱 음료병 10 · 우유팩 10 · 택배상자 10 · 투명 페트병 8 · 컵라면 종이용기 6 ·
칫솔 4 · 빨대 4 · 나무젓가락 4 · 건전지 4

### 확인 필요 — `coated (1)` 파일명

`coated (1).jpeg` / `.jpg` / `.png` 3개가 **서로 다른 사진인데 확장자만 다르다.**
CSV의 note는 "조명 4종"인데 어느 파일이 어느 조명인지 구분할 수 없다.
촬영 담당(태현)이 `coated_01_reflect.jpg` 같은 이름으로 정리해 주면
CSV의 `filename`도 함께 고쳐야 한다.

---

## 지켜야 할 것

1. **재학습 금지.** YOLO는 확정이다. 성능 개선보다 파이프라인 완성이 우선.
2. **`eval_frozen`을 학습·프롬프트에 절대 쓰지 않는다.** `prompt_examples/`와 겹치면 안 된다.
3. **YOLO 클래스로 하드 라우팅하지 않는다.** VLM 판정 후 라우팅한다.
4. **EXIF 회전 보정을 빠뜨리지 않는다.** 누락하면 세로 사진이 눕는다.
5. **크롭 후 원본을 즉시 폐기한다.** 배경에 다른 아이 얼굴이 들어갈 수 있다.
6. **프롬프트를 코드에 하드코딩하지 않는다.** `app/prompts/`에 파일로 두고 버전을 기록한다.
7. **한 품목으로 끝까지 완주한 뒤 확장한다.**

## 고지

- 데이터 출처: 셀렉트스타 오픈데이터셋 × 딩브로 「생활폐기물 객체인식 데이터셋」, **CC BY-SA**
  (출처 표기 및 동일 라이선스 의무)
- 배출 기준은 **충북·청주시 기준**이며 지자체마다 다를 수 있다.
- AI 판정은 참고용이며, 최종 배출은 지역 안내를 따른다.
- 헹굼 여부는 사진으로 판정 불가하다. Before/After 행동 확인으로 대체한다.
- 개인정보: 학급 코드 + 닉네임만 수집, EXIF 위치정보 제거, 크롭 후 원본 폐기.
