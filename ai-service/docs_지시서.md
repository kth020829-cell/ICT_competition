# 다시봄 스쿨 — AI 서비스 구현 지시서

## 0. 이 문서의 사용법

Claude Code에 이 문서 전체를 붙여넣고 시작한다. 섹션 9의 순서대로 진행하며, 한 단계가 끝날 때마다 동작을 확인하고 다음으로 넘어간다.

---

## 1. 프로젝트 개요

**서비스**: 초등 고학년(4~6학년) 대상 재활용 교육 웹앱. 아이가 폐기물을 촬영하면 AI가 종류와 배출 준비 상태를 판정하고, 준비 행동(라벨 제거·헹굼 등)을 안내한다. 준비 후 다시 찍은 사진과 비교해 개선을 확인하고 보상을 준다.

**대회**: 제13회 전국 ICT 융합 AI 공모전 (마감 8/28). 완성된 프로토타입에 가산점.

**팀**: 3인. 이 문서는 AI 파트 담당자용.

**핵심 설계 원칙**
- YOLO는 **검출·크롭 담당**이며 클래스는 **힌트로만** 쓴다. 종류와 상태의 최종 판정은 VLM이 한다.
- 헹굼 여부는 사진으로 판정 불가하다. 따라서 "깨끗한가"를 심판하지 않고 **Before/After 두 장으로 "준비 행동을 했는가"**를 확인한다.
- 판정 불가한 항목은 단정하지 말고 **확인 방법을 안내**한다. (한계를 교육 콘텐츠로 전환)

---

## 2. 이미 확정된 자산 (변경 금지)

### 2.1 YOLO 모델

| 항목 | 값 |
|---|---|
| 파일 | `dasibom_v1_best.pt` (ONNX 변환본 병행) |
| 아키텍처 | YOLO11n |
| 학습 | 25 epoch, imgsz=640, batch=32 |
| 데이터 | 셀렉트스타 × 딩브로 「생활폐기물 객체인식 데이터셋」 29,469장 / 58,059 어노테이션 (CC BY-SA) |
| 성능 (test 2,947장) | mAP50 **0.492**, mAP50-95 0.351 |
| 추론 속도 | 2.3ms/image (T4 기준) |

**클래스별 mAP50**: pet 0.670 / paper 0.636 / can 0.522 / vinyl 0.473 / plastic 0.438 / glass 0.396 / pack 0.310

**재학습하지 말 것.** 이 모델로 확정이며, 성능 개선보다 파이프라인 완성이 우선이다.

### 2.2 YOLO 클래스 (7종, 고정)

```python
YOLO_CLASSES = ["paper", "pack", "can", "glass", "pet", "plastic", "vinyl"]
# 인덱스: 0=paper, 1=pack, 2=can, 3=glass, 4=pet, 5=plastic, 6=vinyl
```

`general_waste` / `etc` 클래스는 **존재하지 않는다.** 미검출 또는 저신뢰도는 VLM 단독 판정 경로로 라우팅한다.

### 2.3 VLM

Claude API (Haiku 우선, 실패 시 Sonnet). **파인튜닝하지 않는다.** 프롬프트 설계와 few-shot 예시만으로 동작시킨다.

---

## 3. 도감 28종 → 클래스 매핑

```python
ITEM_TO_CLASS = {
    # pet
    "투명 페트병": "pet", "플라스틱 음료병": "pet",
    # plastic
    "배달 플라스틱 용기": "plastic", "칫솔": "plastic", "빨대": "plastic",
    "샤프심통": "plastic", "볼펜": "plastic", "페트병 뚜껑": "plastic",
    # can
    "알루미늄캔": "can", "철캔": "can",
    # glass
    "유리병": "glass",
    # pack
    "우유팩": "pack",
    # paper
    "택배상자": "paper", "신문지": "paper", "공책": "paper",
    "계란판": "paper", "영수증": "paper", "코팅지": "paper",
    "스프링노트": "paper", "컵라면 종이용기": "paper",
    # vinyl
    "과자봉지": "vinyl", "에어캡": "vinyl", "페트병 라벨": "vinyl",
    "아이스크림 포장지": "vinyl", "오염된 비닐": "vinyl",
    # VLM 단독 (YOLO 미대응)
    "건전지": None, "아이스팩": None, "나무젓가락": None, "부러진 연필": None,
}
```

**폴백 4종**(건전지·아이스팩·나무젓가락·부러진 연필)은 배출 결론이 상태와 무관하게 고정되므로 검출 단계를 건너뛰고 VLM에 원본을 직접 전달한다. 한계가 아니라 연산 절약 설계로 서술한다.

**제외 항목**: 스티로폼 용기(학습 데이터에 클래스 없음), 깨진 유리·도자기(아동 안전), 지우개가루(객체 검출 불가).

---

## 4. 판정 규칙 (프롬프트 설계 근거)

### 4.1 오염 판정 — 단순 기준

> 용기 안에 **건더기·국물·음식물이 남아 있는지만** 판단한다. 기름기, 물기, 색이 밴 자국, 옅은 얼룩은 정상이며 세척 완료로 인정한다.

절대적 청결도를 심판하지 않는다. 결벽하게 굴면 제대로 씻은 것도 반려되어 아이가 이탈한다.

### 4.2 Before/After 비교

> After를 절대 기준으로 심판하지 말고 Before와 비교한다. 오염이 눈에 띄게 줄었으면 세척 완료로 인정한다.

### 4.3 Before 단계의 올바른 응답

Before 사진에 대한 정답은 배출 결론이 아니라 **"준비 필요 안내"**다. 여기서 곧장 "재활용 가능"이라고 결론 내리면 오답이다.

### 4.4 품목별 특수 규칙

| 품목 | 규칙 |
|---|---|
| 택배상자 | 테이프 제거 흔적(표면 벗겨짐, 접착제 자국)은 오염이 아니다. **테이프 자체가 남아 있는지만** 판단한다. 접었는지는 판정 대상이 아니다. |
| 투명 페트병 | 압착 후 **뚜껑을 닫아서** 배출한다. (유색 페트·기타 병의 뚜껑만 분리) |
| 코팅지 | 완전 라미네이팅만 취급. 애매하면 단정하지 말고 안내: "가장자리를 살짝 찢어봐. 비닐 막이 늘어나면서 벗겨지면 코팅지라 일반쓰레기야." |
| 아이스팩 | 젤/물 두 유형 모두 흔하고 결론이 다르다. **사용자 선택 UI로 분기**시킨다. |
| 계란판 | 종이/플라스틱 재질 먼저 확인 후 분기. |
| 영수증 | 감열지로 간주, 항상 일반쓰레기. 종류 구분 불필요. |

---

## 5. API 스펙

### 5.1 구조

```
프론트엔드 → 백엔드 메인 → AI 추론 서버 → JSON → 백엔드 검증·보상 → 프론트엔드
```

프론트엔드가 AI 서버를 직접 호출하지 않는다.

### 5.2 공통 코드값

```python
STATE_VALUES = ["yes", "no", "unknown", "not_applicable"]

ACTION_CODES = [
    "EMPTY_CONTENT", "RINSE", "REMOVE_LABEL", "REMOVE_CAP",
    "SEPARATE_MATERIALS", "FLATTEN", "CRUSH", "FOLD",
    "DISPOSE_GENERAL", "ASK_ADULT",
]
```

AI는 자유 문자열만 반환하지 않고 반드시 코드도 함께 반환한다. 백엔드가 이 코드로 미션·뱃지를 판정한다.

### 5.3 품목별 states 스키마

모든 품목에 동일한 상태 키를 강제하지 않는다. 해당 없는 항목은 `not_applicable`로 반환한다.

```python
STATE_SCHEMA = {
    "pet":     ["labelAttached", "capAttached", "contentRemaining", "flattened"],
    "plastic": ["labelAttached", "contentRemaining", "contaminated"],
    "can":     ["contentRemaining", "contaminated", "flattened"],
    "glass":   ["capAttached", "contentRemaining"],
    "pack":    ["contentRemaining", "rinsed", "unfolded"],
    "paper":   ["tapeAttached", "contaminated", "coated"],
    "vinyl":   ["contentRemaining", "contaminated"],
}
```

### 5.4 입력

`multipart/form-data`로 이미지 + 아래 필드.

```json
{
  "scanSessionId": "scan_01JABC123",
  "phase": "BEFORE",
  "regionCode": "KR-43-CHEONGJU",
  "expectedClass": null,
  "beforeAnalysisId": null
}
```

### 5.5 출력

```json
{
  "analysisId": "analysis_01XYZ",
  "scanSessionId": "scan_01JABC123",
  "phase": "BEFORE",
  "status": "ACTION_REQUIRED",
  "safety": {
    "faceDetected": false,
    "isWasteImage": true
  },
  "detection": {
    "classCode": "pet",
    "classNameKo": "페트병",
    "itemNameKo": "투명 페트병",
    "confidence": 0.93,
    "source": "yolo",
    "boundingBox": {"x": 0.18, "y": 0.12, "width": 0.61, "height": 0.74}
  },
  "states": {
    "labelAttached": {"value": "yes", "confidence": 0.89},
    "capAttached": {"value": "yes", "confidence": 0.94},
    "contentRemaining": {"value": "no", "confidence": 0.72},
    "flattened": {"value": "no", "confidence": 0.83}
  },
  "requiredActions": [
    {"code": "REMOVE_LABEL", "labelKo": "라벨 떼기", "required": true},
    {"code": "CRUSH", "labelKo": "납작하게 누르기", "required": true}
  ],
  "disposal": {
    "categoryCode": "CLEAR_PET_BIN",
    "categoryNameKo": "투명 페트병 전용함",
    "ruleId": "CHEONGJU-PET-001"
  },
  "feedback": {
    "title": "페트병을 찾았어!",
    "message": "라벨을 떼고 납작하게 눌러보자.",
    "ttsText": "페트병을 찾았어. 라벨을 떼고 납작하게 눌러보자."
  },
  "processing": {
    "usedVlm": true,
    "cacheHit": false,
    "elapsedMs": 2840,
    "modelVersion": "yolo11n-dasibom-1.0.0",
    "promptVersion": "child-feedback-0.1.0",
    "ruleVersion": "recycling-rules-2026-01"
  }
}
```

`detection.source`는 `"yolo"` 또는 `"vlm_only"`(폴백 경로)를 나타낸다.
`itemNameKo`는 VLM이 판정한 세부 품목명이며, `classNameKo`(YOLO 클래스)보다 우선한다.

### 5.6 Before/After 비교

```json
{
  "phase": "AFTER",
  "status": "PARTIALLY_IMPROVED",
  "comparison": {
    "sameClass": true,
    "improvedActions": ["REMOVE_LABEL"],
    "remainingActions": ["CRUSH"],
    "regressedActions": []
  },
  "rewardEligible": false
}
```

`rewardEligible`은 참고값이며 실제 보상 지급은 백엔드가 결정한다.

### 5.7 오류 코드

| 코드 | 의미 | 재시도 |
|---|---|---|
| `FACE_DETECTED` | 얼굴 포함 | 가능 |
| `NOT_WASTE` | 쓰레기 미검출 | 가능 |
| `MULTIPLE_OBJECTS` | 여러 물체 | 가능 |
| `LOW_CONFIDENCE` | 신뢰도 부족 → VLM 폴백 시도 후에도 실패 | 가능 |
| `IMAGE_TOO_DARK` | 너무 어두움 | 가능 |
| `IMAGE_TOO_BLURRY` | 흔들림 | 가능 |
| `CLASS_MISMATCH` | Before/After 품목 불일치 | 가능 |
| `AI_TIMEOUT` | 시간 초과 | 가능 |
| `VLM_UNAVAILABLE` | VLM 장애 | 캐시 사용 |
| `INVALID_AI_OUTPUT` | JSON 파싱 실패 | 서버 재처리 |

---

## 6. 파이프라인

```
1. 이미지 수신
2. EXIF 회전 보정 (exif_transpose) ← 필수. 누락 시 세로 사진이 눕는다
3. EXIF GPS 등 메타데이터 제거 ← 아동 개인정보
4. 품질 검사 (블러 스코어, 밝기) → 미달 시 재촬영 유도
5. 얼굴 검출 (MediaPipe BlazeFace) → 검출 시 REJECTED
6. YOLO 추론
   ├─ conf ≥ 0.35 → 크롭 → 7단계
   └─ conf < 0.35 또는 미검출 → 원본 전체를 VLM에 전달 (폴백 경로)
7. 캐시 조회 (이미지 해시 + phase)
8. VLM 상태 판정 (크롭 이미지 + 품목별 프롬프트)
9. RAG 배출 기준 결합 (충북·청주 기준)
10. 아동 언어 피드백 생성 + TTS 텍스트
11. AFTER인 경우 Before 결과와 비교
```

**7단계 크롭 후 원본 즉시 폐기.** 배경에 다른 아이 얼굴이 들어갈 수 있으므로, 크롭 이미지만 VLM에 전달한다.

---

## 7. 평가 (가장 중요)

### 7.1 동결 평가셋

`eval_frozen/` 110장 (Before 41 / After 41 / Single 28). **절대 학습에 사용하지 않는다.** 성능이 나쁘게 나와도 학습에 넣지 않는다. 이 데이터가 프로젝트의 유일한 성능 근거다.

`prompt_examples/`(VLM few-shot용)와 **절대 겹치지 않는다.**

### 7.2 CSV 스키마

`eval_frozen/eval_frozen_labels.csv`

| 컬럼 | 설명 |
|---|---|
| `filename` | 파일명 (공백·괄호 포함 가능, 실제 파일명과 정확히 일치) |
| `item` | 품목명 |
| `yolo_class` | 기대 클래스 (`(폴백)`이면 YOLO 평가 제외) |
| `pair_id` | Before/After 짝 식별자 (단일 촬영은 공백) |
| `phase` | `before` / `after` / `single` |
| `state` | 촬영 시 실제 상태 |
| `expected` | 정답 결론 |
| `assignee` | 촬영 담당 |
| `note` | 의도적 예외만 기록 |

**Before 행의 `expected`는 "준비 필요 안내"다.** 배출 결론이 아니다.

### 7.3 평가 스크립트가 산출할 지표

```
1. YOLO 검출률       — 크롭이 생성된 비율 (폴백 4종 제외)
2. YOLO 클래스 정확도 — 참고 지표 (틀려도 VLM이 교정하므로 서비스 영향 작음)
3. VLM 품목 정확도   — itemNameKo가 CSV item과 일치
4. VLM 상태 정확도   — states가 CSV state와 일치
5. 최종 결론 정확도  — 가장 중요. expected와 일치하는 비율
6. Before/After 판정 — improvedActions가 실제 변화와 일치
7. 평균 응답 시간, VLM 호출 횟수, 캐시 히트율
```

`scripts/evaluate.py`가 위를 계산하고 **품목별 표 + 오답 목록**을 출력하도록 구현한다. 결과는 기획서와 발표에 그대로 들어간다.

---

## 8. 디렉토리 구조

```
ai-service/
├── app/
│   ├── main.py
│   ├── api/            analyze.py, compare.py, health.py
│   ├── schemas/        request.py, response.py, enums.py
│   ├── services/       detector.py, cropper.py, safety.py,
│   │                   state_analyzer.py, before_after.py,
│   │                   rag.py, feedback.py, cache.py
│   ├── models/weights/ dasibom_v1_best.pt / .onnx
│   ├── prompts/        state_analysis.txt, child_feedback.txt,
│   │                   items/{item}.txt
│   └── rules/          recycling_rules.json  (충북·청주 기준)
├── eval_frozen/        images/, eval_frozen_labels.csv
├── prompt_examples/    (eval_frozen과 중복 금지)
├── scripts/            evaluate.py, export_onnx.py, benchmark_cpu.py
├── tests/
├── requirements.txt
└── README.md
```

모델 코드 · API · 응답 스키마 · 프롬프트 · 배출 기준을 파일로 분리한다. 프롬프트를 코드에 하드코딩하지 않는다.

---

## 9. 구현 순서

각 단계가 끝나면 동작을 확인하고 다음으로 넘어간다. **한 번에 전부 만들지 않는다.**

### STEP 1 — Mock 서버
FastAPI 스켈레톤 + Pydantic 스키마 + 고정 JSON 반환. 백엔드 담당자가 즉시 연동을 시작할 수 있게 한다. `AI_MODE=mock|remote|cached` 환경변수 분기.

Mock 시나리오: `pet_action_required`, `pet_completed`, `after_success`, `after_partial`, `face_detected`, `not_waste`, `multiple_objects`, `low_confidence`, `ai_timeout`.

### STEP 2 — 전처리 + YOLO 검출
EXIF 보정 → 메타데이터 제거 → 품질 검사 → YOLO 추론 → 크롭 저장. `/v1/analyze`가 실제 `detection`을 반환하게 한다. 이 시점에 `states`는 아직 mock.

### STEP 3 — 안전 필터
MediaPipe BlazeFace 얼굴 검출. 검출 시 `REJECTED` + `FACE_DETECTED`. 크롭 후 원본 폐기 로직 포함.

### STEP 4 — VLM 상태 판정 (투명 페트병 1종만)
품목 하나로 끝까지 완주한다. 프롬프트 파일 분리, JSON 강제 출력, 파싱 실패 시 재시도. 여기서 나오는 문제(응답 지연, JSON 깨짐, 과도한 엄격함)가 진짜 병목이다.

### STEP 5 — RAG + 피드백 생성
`recycling_rules.json` 조회 → 아동 언어 피드백 + TTS 텍스트. **RAG 라우팅은 YOLO 클래스가 아니라 VLM 판정 품목명으로 한다.**

### STEP 6 — 평가 스크립트
`scripts/evaluate.py` 구현 후 페트병 관련 행만으로 1차 측정. 이 시점에 숫자가 처음 나온다.

### STEP 7 — 나머지 품목 확장
품목별 프롬프트 추가. 폴백 4종(건전지·아이스팩·나무젓가락·부러진 연필)의 VLM 단독 경로 구현.

### STEP 8 — Before/After 비교
`beforeAnalysisId` 연결, `improvedActions`/`remainingActions` 계산, `CLASS_MISMATCH` 처리.

### STEP 9 — 캐시 + 오프라인 폴백
이미지 해시 기반 캐시. VLM 장애 시 캐시 응답. 발표용 `AI_MODE=cached` 완비.

### STEP 10 — ONNX 변환 + CPU 벤치마크
노트북 로컬 서버 배포용. INT8 양자화. 실제 데모 기기에서 응답 시간 측정.

### STEP 11 — 전체 평가셋 측정
110장 전량으로 최종 지표 산출. 기획서 반영.

---

## 10. 배포

노트북 로컬 FastAPI 서버 + Cloudflare Tunnel(HTTPS). 휴대폰에서 접속해 카메라 사용.

카메라 입력은 `getUserMedia`가 아니라 `<input type="file" accept="image/*" capture="environment">`를 쓴다. iOS Safari 호환성이 훨씬 안정적이고 네이티브 카메라 앱을 띄워 화질도 좋다.

업로드 전 클라이언트에서 긴 변 1024px로 리사이즈한다.

---

## 11. 반드시 지킬 것

1. **재학습 금지.** YOLO는 확정. 성능 개선보다 파이프라인 완성이 우선.
2. **eval_frozen을 학습·프롬프트에 절대 사용하지 않는다.**
3. **YOLO 클래스로 하드 라우팅하지 않는다.** pack이 0.310이므로 클래스를 결정으로 쓰면 그대로 서비스 오류가 된다. VLM 판정 후 라우팅한다.
4. **EXIF 회전 보정을 빠뜨리지 않는다.**
5. **크롭 후 원본을 즉시 폐기한다.** (아동 개인정보)
6. **프롬프트를 코드에 하드코딩하지 않는다.** 파일로 분리하고 버전을 기록한다.
7. **한 품목으로 끝까지 완주한 뒤 확장한다.**

---

## 12. 앱·기획서에 명시할 고지 사항

| 대상 | 내용 |
|---|---|
| 데이터 출처 | 셀렉트스타 오픈데이터셋 × 딩브로, CC BY-SA. 출처 표기 및 동일 라이선스 의무 |
| 지역 기준 | 배출 기준은 충북·청주시 기준이며 지자체마다 다를 수 있음 |
| 참고용 안내 | AI 판정은 참고용, 최종 배출은 지역 안내를 따를 것 |
| 판정 불가 | 헹굼 여부는 사진으로 판정 불가 → Before/After 행동 확인으로 대체 |
| 미검출 품목 | 4종은 검출 없이 VLM 단독 판정 |
| 개인정보 | 학급 코드 + 닉네임만 수집, EXIF 위치정보 제거, 크롭 후 원본 폐기 |
| 안전 | 날카로운 캔 뚜껑은 어른과 함께, 건전지 분해 금지 |
| 평가 | 110장은 학습 미사용, 성능 수치는 이 동결셋 기준 |
