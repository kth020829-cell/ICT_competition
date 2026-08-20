# 다시봄 스쿨

> 찍고, 고치고, 다시 보며 배우는 AI 카메라 기반 어린이 분리배출 교육 플랫폼

다시봄 스쿨은 학생이 생활 속 쓰레기를 촬영하면 AI가 품목과 상태를 판정하고, 학생이 안내에 따라 직접 분리배출 상태를 고친 뒤 다시 촬영하며 올바른 행동을 익히는 체험형 환경교육 서비스입니다. 학생에게는 도감·경험치·캐릭터·미션을 제공하고, 교사에게는 익명화된 학급 활동 현황과 교육 콘텐츠 관리 기능을 제공합니다.

이 문서는 **프론트엔드, 백엔드, AI/Jetson을 포함한 전체 프로젝트의 개발 기준서**입니다.

> 현재 저장소에는 프론트엔드 프로토타입만 구현되어 있습니다. 백엔드와 AI/Jetson 부분은 팀이 바로 개발을 시작할 수 있도록 권장 구조, 책임 범위, 인터페이스와 개발 순서를 정의한 설계안입니다.

## 목차

- [프로젝트 목표](#프로젝트-목표)
- [현재 개발 상태](#현재-개발-상태)
- [핵심 사용자 흐름](#핵심-사용자-흐름)
- [전체 시스템 구조](#전체-시스템-구조)
- [기술 스택](#기술-스택)
- [팀별 역할](#팀별-역할)
- [권장 모노레포 구조](#권장-모노레포-구조)
- [로컬 실행](#로컬-실행)
- [프론트엔드](#프론트엔드)
- [백엔드](#백엔드)
- [AI와 Jetson](#ai와-jetson)
- [API 계약](#api-계약)
- [데이터 모델](#데이터-모델)
- [환경 변수](#환경-변수)
- [테스트 전략](#테스트-전략)
- [GitHub 협업](#github-협업)
- [배포 구조](#배포-구조)
- [보안과 개인정보](#보안과-개인정보)
- [개발 로드맵](#개발-로드맵)

## 프로젝트 목표

### 교육 목표

- 정답을 암기하는 대신 실제 물건을 직접 고쳐보게 합니다.
- AI 결과를 단순 판정이 아니라 행동 안내로 연결합니다.
- 개인 경쟁보다 학급 공동 목표와 환경 행동의 누적을 강조합니다.
- 지역에서 자주 접하는 분리배출 사례를 교육 콘텐츠로 제공합니다.

### 제품 목표

- 학생은 실명이나 이메일 없이 학급 코드와 닉네임으로 참여합니다.
- 촬영부터 AI 판정까지 기다림과 실패를 어린이가 이해할 수 있게 안내합니다.
- 교사는 학생 개인의 민감정보 없이 학급 수준의 학습 변화를 확인합니다.
- AI 또는 네트워크 장애가 발생해도 재시도와 복구가 가능합니다.

## 현재 개발 상태

| 영역 | 상태 | 내용 |
| --- | --- | --- |
| 프론트엔드 P0 | 구현 | 학급 참여, 카메라, Before/After 판정, 행동 안내, 보상, 도감 |
| 프론트엔드 P1 | 구현 | 미션, 캐릭터, 뱃지, 공동 목표, 체크리스트, 교사 화면 |
| 프론트엔드 P2 | 구현 | 오프라인, 세션 복구, AI 지연 복구, 충북 콘텐츠, 운영 설정 |
| 카메라 | 구현 | 브라우저 카메라 요청, 1280×1280 JPEG 캡처 |
| AI 판정 | Mock | 고정된 투명 페트병 Before/After 결과 사용 |
| 인증 | Mock | 학급 코드와 교사 로그인 UI만 구현 |
| 백엔드 | 미구현 | 아래 설계를 기준으로 신규 개발 필요 |
| AI 모델 | 미구현 | 데이터 수집·학습·평가·변환 필요 |
| Jetson 추론 서버 | 미구현 | 장비 설정과 추론 API 개발 필요 |
| 운영 데이터베이스 | 미구현 | PostgreSQL 또는 배포 환경 DB 구성 필요 |
| 이미지 저장소 | 미구현 | S3/R2 호환 Object Storage 구성 필요 |

학생 데모 코드는 `4B7K2M`이며, 교사 체험 계정은 `teacher@dasibom.school` / `demo1234`입니다. 현재 체험 정보는 실제 인증 정보가 아닙니다.

## 핵심 사용자 흐름

### 학생

```text
서비스 진입
  → 학급 코드 입력
  → 익명 닉네임 설정
  → 학생 홈
  → 쓰레기 Before 촬영
  → 이미지 업로드
  → AI 품목·상태 분석
  → 행동 안내
  → 학생이 실제 쓰레기 상태 교정
  → After 재촬영
  → AI 교정 여부 확인
  → 보상 트랜잭션 처리
  → 도감·XP·미션·학급 목표 갱신
```

### 교사

```text
교사 로그인
  → 담당 학급 선택
  → 참여 학생·판정·교정 완료율 확인
  → 많이 헷갈린 품목 확인
  → 미션 및 지역 콘텐츠 관리
  → 학급 코드 재발급 또는 참여 잠금
  → 공동 목표 인증서 발급
```

### 장애 복구

```text
이미지 업로드 실패 → 같은 파일로 재시도
AI 처리 지연 → 작업 ID로 상태 재조회
Jetson 오프라인 → 서버 대체 모델 또는 잠시 후 재시도
브라우저 종료 → 30분 이내 촬영 세션 복구
중복 요청 → 멱등성 키로 보상과 작업 중복 방지
```

## 전체 시스템 구조

```text
┌──────────────────────────────┐
│ Student / Teacher Web Client │
│ React + TypeScript + Vinext  │
└──────────────┬───────────────┘
               │ HTTPS REST / SSE
               ▼
┌──────────────────────────────┐
│ Backend API                  │
│ FastAPI + Python             │
│ Auth · Class · Scan · Reward │
└──────┬──────────┬────────────┘
       │          │
       │          ├───────────────► PostgreSQL
       │          ├───────────────► Redis / Job Queue
       │          └───────────────► S3/R2 Image Storage
       │
       ▼
┌──────────────────────────────┐
│ AI Inference Gateway         │
│ Contract validation · routing│
└──────────────┬───────────────┘
               │ Internal network
               ▼
┌──────────────────────────────┐
│ NVIDIA Jetson                │
│ PyTorch/ONNX/TensorRT        │
│ Detection · Classification   │
└──────────────────────────────┘
```

프론트엔드는 Jetson에 직접 접근하지 않습니다. 백엔드가 인증, 작업 큐, 재시도, 결과 검증, 기록과 보상을 담당하고 Jetson은 추론에 집중합니다.

## 기술 스택

아래 스택은 현재 프론트엔드와 권장 백엔드·AI 구성을 합친 기준안입니다.

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| Frontend | TypeScript, React 19, Vinext, Vite | 학생·교사 웹 애플리케이션 |
| Styling | CSS | 반응형 UI, 접근성, 인쇄 화면 |
| Backend | Python 3.12, FastAPI, Pydantic | REST API, 인증, 비즈니스 로직 |
| ORM/Migration | SQLAlchemy 2, Alembic | 데이터 접근과 스키마 변경 |
| Database | PostgreSQL | 사용자, 학급, 판정, 보상, 콘텐츠 |
| Cache/Queue | Redis, Celery 또는 ARQ | AI 작업 큐와 임시 상태 |
| Storage | Cloudflare R2 또는 S3 | 제한 시간 촬영 이미지 저장 |
| AI Training | Python, PyTorch, Ultralytics/torchvision | 모델 학습과 평가 |
| AI Runtime | ONNX Runtime, TensorRT | Jetson 최적화 추론 |
| Jetson API | FastAPI 또는 gRPC | 내부 추론 인터페이스 |
| Container | Docker, Docker Compose | 동일한 개발·운영 환경 |
| Monitoring | Sentry, Prometheus, Grafana | 오류와 성능 관찰 |
| CI/CD | GitHub Actions | Lint, Test, Build, 배포 자동화 |

AI 모델 종류는 데이터셋과 정확도 실험 후 확정합니다. 한 모델에 모든 책임을 넣기보다 품목 탐지/분류와 상태 판정을 분리할 수 있습니다.

## 팀별 역할

### 프론트엔드 팀

- 학생·교사 화면, 반응형 레이아웃과 접근성 구현
- 카메라 권한, 촬영, 압축, 미리보기와 재촬영
- 학급 참여와 익명 세션 유지
- Presigned URL을 이용한 이미지 업로드
- 분석 작업 생성, 폴링 또는 SSE 결과 수신
- 로딩·저신뢰도·미지원 품목·오프라인·타임아웃 화면
- Before/After가 같은 `scanSessionId`를 사용하도록 관리
- 도감, XP, 뱃지, 미션, 공동 목표 API 연동
- 교사 인증, 권한 가드와 대시보드 연동
- 컴포넌트 테스트와 브라우저 E2E 테스트

프론트엔드 상세 내용은 [frontend/README.md](./frontend/README.md)를 참고합니다.

### 백엔드 팀

- 학생 익명 세션과 교사 인증·인가
- 학급 코드 생성, 참여, 재발급, 잠금
- 촬영 세션과 분석 작업 상태 머신
- 이미지 업로드 URL 발급과 보존 기간 관리
- Redis 작업 큐를 통한 Jetson 추론 요청
- Jetson 응답 스키마 검증과 실패 복구
- Before/After 결과 비교와 교정 성공 확정
- XP, 도감 카드, 뱃지, 미션 보상의 원자적 처리
- 학급 통계와 교사 대시보드 집계
- 콘텐츠 게시·초안·지역 필터 관리
- 감사 로그, Rate Limit, 모니터링과 운영 도구
- OpenAPI 문서와 테스트용 Mock 서버 제공

### AI 팀

- 분리배출 품목 및 상태 분류 체계 정의
- 이미지 수집, 익명화, 라벨링 가이드와 데이터 버전 관리
- 학습/검증/테스트 데이터 분리
- 객체 탐지 또는 이미지 분류 모델 학습
- 라벨, 뚜껑, 오염, 압착 등 상태 판정 모델 개발
- 신뢰도 보정과 저신뢰도 기준 설정
- 품목별 Precision, Recall, F1과 상태 판정 성능 평가
- ONNX 변환 및 TensorRT 최적화
- 모델 카드, 버전, 데이터 이력과 실험 결과 기록
- 오판 사례 수집과 재학습 파이프라인 운영

### Jetson 담당

- JetPack, CUDA, cuDNN, TensorRT 버전 고정
- Docker Runtime과 장비 부팅 시 서비스 자동 시작
- 모델 엔진 로딩과 Warm-up
- 내부망 전용 추론 API 및 인증 토큰
- `/health/live`, `/health/ready` 상태 점검
- GPU 메모리, 온도, 전력 모드, 추론 시간 모니터링
- 장비 오프라인과 과열 시 안전한 실패 응답
- 모델 파일 원자적 교체와 이전 버전 Rollback
- 동일 입력에 대한 스키마 일관성 보장

## 권장 모노레포 구조

현재는 `frontend/`만 존재합니다. 백엔드와 AI 개발을 시작할 때 다음 구조를 권장합니다.

```text
dasibom-school/
├── README.md
├── frontend/                    # 현재 React/Vinext 프로젝트
├── backend/
│   ├── app/
│   │   ├── api/v1/             # HTTP 라우터
│   │   ├── core/               # 설정, 보안, 로깅
│   │   ├── models/             # ORM 모델
│   │   ├── schemas/            # Pydantic 요청/응답
│   │   ├── services/           # 도메인 서비스
│   │   ├── repositories/       # DB 접근
│   │   ├── workers/            # AI 비동기 작업
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── ai/
│   ├── configs/                # 학습/추론 설정
│   ├── datasets/               # 코드와 메타데이터만 Git 관리
│   ├── src/
│   │   ├── training/
│   │   ├── inference/
│   │   ├── evaluation/
│   │   └── export/
│   ├── tests/
│   ├── models/README.md        # 가중치 저장 위치와 체크섬
│   ├── pyproject.toml
│   └── Dockerfile
├── jetson/
│   ├── app/                    # 추론 API
│   ├── scripts/                # 설치, 변환, 배포, 헬스체크
│   ├── systemd/                # 자동 시작 설정
│   ├── tests/
│   ├── Dockerfile.jetson
│   └── README.md
├── contracts/
│   ├── openapi.yaml            # 프론트-백엔드 계약
│   ├── inference.schema.json   # 백엔드-AI 계약
│   └── taxonomy.yaml           # 품목·행동 코드 기준표
├── infrastructure/
│   ├── compose.yaml
│   ├── nginx/
│   └── monitoring/
├── docs/
│   ├── architecture.md
│   ├── privacy.md
│   └── runbook.md
└── .github/
    ├── workflows/
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

대용량 원본 이미지와 모델 가중치는 일반 Git에 넣지 않습니다. 데이터셋은 DVC 또는 Object Storage, 모델은 Model Registry나 Release Asset으로 관리하고 버전·체크섬만 저장소에 기록합니다.

## 로컬 실행

### 현재 프론트엔드 실행

필요 조건은 Node.js `22.13.0` 이상입니다.

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

카메라는 `localhost` 또는 HTTPS에서 동작합니다. 카메라 권한이 없어도 `데모 사진`으로 전체 흐름을 확인할 수 있습니다.

### 전체 시스템 실행 목표

백엔드와 AI 서비스가 추가된 후에는 다음처럼 한 번에 개발 환경을 실행하도록 구성합니다.

```bash
docker compose -f infrastructure/compose.yaml up --build
```

권장 로컬 서비스 구성:

| Service | 기본 주소 | 설명 |
| --- | --- | --- |
| Frontend | `http://localhost:3000` | 학생·교사 웹 |
| Backend | `http://localhost:8000` | REST API와 OpenAPI |
| PostgreSQL | `localhost:5432` | 운영 데이터 |
| Redis | `localhost:6379` | 작업 큐와 캐시 |
| MinIO | `http://localhost:9000` | 로컬 S3 호환 이미지 저장소 |
| Mock Inference | `http://localhost:8100` | Jetson 없이 사용하는 추론 Mock |

Jetson이 없는 개발자는 고정 JSON 또는 CPU 모델을 반환하는 Mock Inference를 사용합니다. 이 Mock도 실제 Jetson과 동일한 JSON Schema를 따라야 합니다.

## 프론트엔드

현재 구현 기술은 TypeScript, React 19, Vinext, Vite와 CSS입니다.

주요 파일:

| 파일 | 역할 |
| --- | --- |
| `frontend/app/DasiBomApp.tsx` | 전체 학생·교사 화면 흐름과 상태 |
| `frontend/app/P1Features.tsx` | 미션, 성장, 뱃지, 체크리스트, 교사 기능 |
| `frontend/app/P2Features.tsx` | 네트워크, 복구, 데모 모드 |
| `frontend/app/useCamera.ts` | 카메라와 1280×1280 JPEG 캡처 |
| `frontend/app/useResilience.ts` | 온라인 감지, 30분 세션 복구, SW 등록 |
| `frontend/app/mockData.ts` | 현재 Mock AI 판정과 도감 데이터 |
| `frontend/app/types.ts` | 화면, 분석, 행동, 도감 타입 |

현재 하나의 `Screen` 상태로 화면을 바꾸고 있습니다. 실제 서비스 연동 단계에서는 URL 라우팅과 서버 상태 관리 계층으로 분리해야 합니다.

## 백엔드

### 권장 도메인 모듈

- `auth`: 교사 로그인, Access/Refresh Token, 권한
- `classes`: 학급, 참여 코드, 잠금, 담당 교사
- `students`: 익명 학생 세션과 닉네임
- `scans`: 촬영 세션, Before/After 이미지와 상태
- `analyses`: AI 작업 생성, 폴링, 결과 저장
- `rewards`: XP, 카드, 뱃지와 중복 지급 방지
- `missions`: 일일 미션, 진행률, 완료 처리
- `collections`: 도감 품목과 획득 기록
- `contents`: 교육 문구, 지역 특화 콘텐츠, 게시 상태
- `dashboards`: 학급 통계와 혼동 품목 집계
- `operations`: 장비 상태, 작업 재처리, 감사 로그

### 촬영 세션 상태 머신

```text
CREATED
  → BEFORE_UPLOADED
  → BEFORE_PROCESSING
  → ACTION_REQUIRED
  → AFTER_UPLOADED
  → AFTER_PROCESSING
  → COMPLETED
  → REWARDED
```

실패 상태는 `UPLOAD_FAILED`, `ANALYSIS_FAILED`, `EXPIRED`, `CANCELLED`로 구분합니다. 실패 후 재시도할 때는 기존 세션과 작업 이력을 유지합니다.

### 백엔드 핵심 규칙

- 모든 분석 생성 요청에 멱등성 키를 적용합니다.
- 보상 지급은 데이터베이스 트랜잭션과 고유 제약조건으로 한 번만 처리합니다.
- 브라우저의 XP나 완료 여부를 신뢰하지 않고 서버가 판정 결과를 기준으로 계산합니다.
- Jetson 응답은 JSON Schema 또는 Pydantic으로 검증한 뒤 저장합니다.
- 이미지 원본은 기본적으로 짧은 보존 기간 후 자동 삭제합니다.
- 교사 API는 담당 학급에 대한 권한을 매 요청마다 확인합니다.
- 학생 개인 순위보다 익명 활동과 학급 집계를 제공합니다.

## AI와 Jetson

### 품목 분류 체계 예시

```yaml
pet_transparent:
  display_name_ko: 투명 페트병
  required_states:
    - label_removed
    - cap_removed
    - crushed

paper_box:
  display_name_ko: 종이 상자
  required_states:
    - tape_removed
    - flattened

beverage_can:
  display_name_ko: 음료 캔
  required_states:
    - emptied
    - rinsed
```

화면 문구와 AI 클래스명을 직접 결합하지 않습니다. `taxonomy.yaml`의 고정 코드가 프론트, 백엔드, AI의 공통 기준이 되고 한국어 문구는 콘텐츠 계층에서 관리합니다.

### AI 파이프라인

```text
데이터 수집
  → 개인정보 제거 및 품질 검사
  → 품목/Bounding Box/상태 라벨링
  → 데이터셋 버전 고정
  → 모델 학습
  → 품목별·상태별 평가
  → 오류 분석
  → ONNX Export
  → TensorRT Engine 생성
  → Jetson Benchmark
  → Staging 배포
  → 운영 모니터링 및 재학습
```

### 평가 기준

- 품목 탐지: mAP50, mAP50-95, 클래스별 Precision/Recall
- 품목 분류: Macro F1, 클래스별 Recall, Confusion Matrix
- 상태 판정: 행동별 Precision/Recall/F1
- 신뢰도: Calibration Error와 저신뢰도 거절 성능
- 성능: P50/P95 추론 시간, FPS, GPU 메모리
- 운영: 미지원 품목 비율, 재촬영 비율, 오판 신고 비율

정확도 목표는 전체 평균 하나로만 정하지 않고 품목별 최소 Recall과 위험한 오안내의 최대 허용률을 함께 정합니다.

### Jetson 입력 규격

| 항목 | 기준 |
| --- | --- |
| 전송 | 내부 HTTPS 또는 gRPC |
| Content-Type | `image/jpeg` 또는 JSON의 제한 시간 이미지 URL |
| 권장 크기 | 현재 프론트 출력 `1280 × 1280` |
| 최대 용량 | 팀 합의 후 서버와 장비에서 동일하게 제한 |
| 단계 | `BEFORE`, `AFTER` |
| 타임아웃 | 연결/추론/전체 타임아웃을 분리 |
| 인증 | 내부 서비스 토큰 또는 mTLS |
| 요청 ID | 모든 로그에 동일한 `requestId` 사용 |

### Jetson 추론 응답 예시

```json
{
  "requestId": "req_01",
  "modelVersion": "waste-state-v1.0.0",
  "taxonomyVersion": "2026-08-01",
  "detections": [
    {
      "classCode": "pet_transparent",
      "confidence": 0.94,
      "bbox": [0.18, 0.12, 0.81, 0.92],
      "states": {
        "label_removed": 0.08,
        "cap_removed": 0.12,
        "crushed": 0.04
      }
    }
  ],
  "quality": {
    "brightness": 0.76,
    "blur": 0.09,
    "objectCount": 1
  },
  "inferenceMs": 428
}
```

Jetson은 최종 교육 문구나 XP를 결정하지 않습니다. 모델의 관측 결과와 품질 정보를 반환하고, 백엔드가 교육 규칙과 콘텐츠를 적용해 프론트엔드용 결과를 만듭니다.

## API 계약

API 기본 버전은 `/api/v1`을 사용하고 계약은 `contracts/openapi.yaml`에서 관리합니다.

### 주요 엔드포인트

| Method | Endpoint | 인증 | 용도 |
| --- | --- | --- | --- |
| `POST` | `/classes/join` | 없음 | 학급 코드로 익명 학생 세션 생성 |
| `POST` | `/auth/teacher/login` | 없음 | 교사 로그인 |
| `POST` | `/auth/refresh` | Refresh | Access Token 갱신 |
| `POST` | `/scan-sessions` | 학생 | 촬영 세션 생성 |
| `POST` | `/uploads/presign` | 학생 | 제한 시간 업로드 URL 발급 |
| `POST` | `/scan-sessions/{id}/analyses` | 학생 | Before/After 분석 작업 생성 |
| `GET` | `/analyses/{id}` | 학생 | 분석 작업 상태와 결과 조회 |
| `GET` | `/me/progress` | 학생 | 레벨, XP, 도감과 뱃지 조회 |
| `GET` | `/missions/today` | 학생 | 오늘의 미션 조회 |
| `GET` | `/classes/{id}/goal` | 학생 | 학급 공동 목표 조회 |
| `GET` | `/teacher/classes/{id}/dashboard` | 교사 | 학급 집계 조회 |
| `GET` | `/teacher/classes/{id}/students` | 교사 | 익명 학생 활동 목록 |
| `PATCH` | `/teacher/classes/{id}/settings` | 교사 | 잠금·비교 설정 변경 |
| `POST` | `/teacher/classes/{id}/join-code` | 교사 | 참여 코드 재발급 |
| `GET` | `/health` | 없음/내부 | 백엔드 상태 확인 |

### 학생 참여 요청

```json
{
  "joinCode": "4B7K2M",
  "nickname": "초록탐험가",
  "deviceId": "local-random-uuid"
}
```

### 학생 참여 응답

```json
{
  "studentSessionId": "student_session_01",
  "class": {
    "id": "class_01",
    "schoolName": "충북초등학교",
    "grade": 4,
    "name": "2반"
  },
  "accessToken": "short-lived-token",
  "expiresIn": 3600
}
```

### 분석 생성 요청

```json
{
  "phase": "BEFORE",
  "imageKey": "scans/scan_01/before.jpg",
  "clientRequestId": "79fd838e-0c22-4bc1-b3aa-3905387e5736"
}
```

### 프론트엔드용 분석 완료 응답

```json
{
  "analysisId": "analysis_01",
  "scanSessionId": "scan_01",
  "phase": "BEFORE",
  "jobStatus": "SUCCEEDED",
  "status": "ACTION_REQUIRED",
  "detection": {
    "classCode": "pet_transparent",
    "classNameKo": "투명 페트병",
    "confidence": 0.94
  },
  "requiredActions": [
    {
      "code": "REMOVE_LABEL",
      "labelKo": "라벨 떼기",
      "description": "비닐 라벨은 병에서 완전히 분리해줘."
    },
    {
      "code": "REMOVE_CAP",
      "labelKo": "뚜껑 분리하기",
      "description": "뚜껑과 고리를 병에서 떼어내자."
    },
    {
      "code": "CRUSH",
      "labelKo": "납작하게 누르기",
      "description": "공기를 빼고 납작하게 눌러줘."
    }
  ],
  "feedback": {
    "title": "페트병을 찾았어!",
    "message": "세 가지만 고치면 멋지게 재활용할 수 있어!",
    "ttsText": "라벨과 뚜껑을 떼고 납작하게 눌러보자."
  },
  "modelVersion": "waste-state-v1.0.0",
  "inferenceMs": 428
}
```

### 공통 오류 형식

```json
{
  "error": {
    "code": "IMAGE_TOO_DARK",
    "message": "사진이 너무 어두워요.",
    "retryable": true,
    "requestId": "req_01",
    "details": {}
  }
}
```

| 오류 코드 | 프론트엔드 처리 |
| --- | --- |
| `INVALID_JOIN_CODE` | 참여 코드 재입력 |
| `CLASS_LOCKED` | 새 참여가 잠겼음을 안내 |
| `IMAGE_TOO_DARK` | 밝은 곳에서 재촬영 |
| `MULTIPLE_OBJECTS` | 한 개만 촬영하도록 안내 |
| `OBJECT_TOO_SMALL` | 가이드 안을 채워 재촬영 |
| `UNSUPPORTED_ITEM` | 미지원 품목 안내와 재촬영 |
| `LOW_CONFIDENCE` | 결과를 단정하지 않고 재촬영 |
| `ANALYSIS_TIMEOUT` | 재시도·캐시·홈 이동 |
| `DEVICE_OFFLINE` | 대체 추론 또는 잠시 후 재시도 |
| `RATE_LIMITED` | 재시도 가능 시간 표시 |

## 데이터 모델

### 핵심 테이블

| 테이블 | 주요 필드 |
| --- | --- |
| `teachers` | id, email, password_hash, status, created_at |
| `schools` | id, name, region_code |
| `classes` | id, school_id, teacher_id, grade, name, locked |
| `class_join_codes` | id, class_id, code_hash, expires_at, revoked_at |
| `student_sessions` | id, class_id, nickname, device_hash, expires_at |
| `scan_sessions` | id, student_session_id, status, started_at, completed_at |
| `scan_images` | id, scan_session_id, phase, object_key, delete_at |
| `analysis_jobs` | id, scan_session_id, phase, status, model_version, error_code |
| `analysis_results` | id, job_id, class_code, confidence, raw_result_json |
| `required_actions` | id, result_id, action_code, completed |
| `reward_transactions` | id, student_session_id, scan_session_id, xp, unique_key |
| `collection_items` | id, class_code, rarity, content_version |
| `student_collections` | student_session_id, item_id, acquired_at |
| `missions` | id, type, rule_json, starts_at, ends_at, status |
| `mission_progress` | mission_id, student_session_id, progress, completed_at |
| `class_goals` | id, class_id, target, current, completed_at |
| `contents` | id, type, locale, region_code, status, payload_json |
| `audit_logs` | id, actor_type, actor_id, action, metadata_json, created_at |

이미지 자체는 DB에 넣지 않고 Object Storage의 키와 삭제 예정 시각만 저장합니다. 분석 원본 JSON은 재현성과 감사에 필요하지만, 개인정보가 섞이지 않도록 저장 전 필터링합니다.

## 환경 변수

### 프론트엔드

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_MODE=development
VITE_ENABLE_MOCK=true
```

### 백엔드

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dasibom
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=<secret>
JWT_ACCESS_TTL_SECONDS=3600
JWT_REFRESH_TTL_SECONDS=1209600
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_BUCKET=dasibom-scans
OBJECT_STORAGE_ACCESS_KEY=<secret>
OBJECT_STORAGE_SECRET_KEY=<secret>
INFERENCE_BASE_URL=http://localhost:8100
INFERENCE_SERVICE_TOKEN=<secret>
SCAN_IMAGE_RETENTION_HOURS=24
```

### Jetson

```dotenv
MODEL_PATH=/models/waste-state.engine
MODEL_VERSION=waste-state-v1.0.0
TAXONOMY_VERSION=2026-08-01
INFERENCE_TOKEN=<secret>
MAX_IMAGE_BYTES=5242880
INFERENCE_TIMEOUT_SECONDS=10
LOG_LEVEL=INFO
```

실제 값이 있는 `.env`, 모델 키, JWT Secret과 장비 토큰은 Git에 커밋하지 않습니다. 각 디렉터리에는 키 이름과 안전한 예시만 담은 `.env.example`을 둡니다.

## 테스트 전략

### 프론트엔드

```bash
cd frontend
npm run lint
npm test
```

- 컴포넌트 렌더링과 접근성
- 학생 참여와 Before/After 흐름
- 카메라 권한 거부와 데모 촬영
- 업로드 실패와 재시도
- AI 처리 지연·실패·저신뢰도
- 오프라인과 세션 복구
- 교사 인증과 권한 없는 접근

### 백엔드

```bash
cd backend
pytest
```

- 도메인 서비스 단위 테스트
- API 통합 테스트
- DB 트랜잭션과 마이그레이션 테스트
- 보상 중복 지급 방지
- 교사 권한과 학급 데이터 격리
- Jetson 타임아웃·잘못된 응답·재시도
- Presigned URL과 이미지 삭제 작업

### AI

```bash
cd ai
pytest
```

- 전처리와 후처리 단위 테스트
- 고정 Golden Image 결과 회귀 테스트
- 모델 Export 전후 정확도 허용 오차
- JSON Schema 계약 테스트
- TensorRT 엔진 출력 일관성
- 품목별 성능 임계값 검사

### 계약 및 E2E

- OpenAPI 변경 시 프론트 타입 생성 테스트
- Jetson 응답의 `inference.schema.json` 검증
- 실제 파일 업로드부터 보상 지급까지 E2E
- 장비 오프라인과 서버 대체 경로 Chaos Test
- 모바일 Chrome/Safari 실기기 카메라 테스트

## GitHub 협업

### 저장소 전략

초기 3인 팀에서는 하나의 모노레포를 권장합니다. 하나의 기능이 프론트, 백엔드, AI 계약을 함께 바꾸는 경우 동일 PR에서 영향을 확인하기 쉽기 때문입니다. 모델 가중치와 데이터셋만 외부 저장소로 분리합니다.

### CODEOWNERS 예시

```text
/frontend/        @frontend-owner
/backend/         @backend-owner
/ai/              @ai-owner
/jetson/          @ai-owner @backend-owner
/contracts/       @frontend-owner @backend-owner @ai-owner
/infrastructure/  @backend-owner
```

`contracts/` 변경은 세 파트 모두의 리뷰를 받도록 Branch Protection을 설정합니다.

### 브랜치 예시

```text
feat/frontend-scan-upload
feat/backend-analysis-job
feat/ai-pet-state-model
feat/jetson-inference-api
fix/reward-idempotency
docs/inference-contract
```

### 커밋 예시

```text
feat(frontend): upload scan image with presigned URL
feat(backend): queue scan analysis jobs
feat(ai): classify transparent PET bottle states
feat(jetson): add TensorRT inference endpoint
fix(backend): prevent duplicate scan rewards
docs(contract): add low-confidence error response
```

### PR 필수 확인

- [ ] 구현 영역과 기획 범위가 일치한다.
- [ ] API 또는 AI 계약 변경이 `contracts/`에 반영됐다.
- [ ] 관련 파트 담당자의 리뷰를 받았다.
- [ ] 정상, 로딩, 빈 상태, 실패와 재시도를 처리했다.
- [ ] 개인정보와 Secret이 코드·데이터·로그에 없다.
- [ ] 해당 영역 Lint, Test, Build가 통과한다.
- [ ] DB 변경에는 마이그레이션과 Rollback 설명이 있다.
- [ ] 모델 변경에는 평가 결과와 모델 버전이 있다.
- [ ] 사용자 화면 변경에는 스크린샷 또는 영상이 있다.

### GitHub Actions 권장 Job

| 변경 경로 | 실행 Job |
| --- | --- |
| `frontend/**` | ESLint, Build, Node Test, E2E |
| `backend/**` | Ruff, Mypy, Pytest, Migration Check |
| `ai/**` | Ruff, Pytest, Contract Test, Lightweight Eval |
| `jetson/**` | Schema Test, Container Build, Jetson Runner Test |
| `contracts/**` | OpenAPI Lint, Codegen Diff, Schema Compatibility |

## 배포 구조

### 개발 환경

- 프론트엔드: 로컬 Vinext 개발 서버
- 백엔드·DB·Redis·MinIO: Docker Compose
- AI: Mock Inference 또는 CPU 추론
- Jetson: 선택적 내부 개발 장비

### Staging

- 프론트엔드: HTTPS 미리보기 배포
- 백엔드: Staging API와 독립 DB
- 이미지: 짧은 수명 Staging Bucket
- AI: 고정 모델 버전 또는 Jetson Staging 장비
- 테스트 계정과 합성 이미지만 사용

### Production

- 프론트엔드: CDN/Edge 배포
- 백엔드: 컨테이너 또는 관리형 런타임, 최소 2개 인스턴스 권장
- PostgreSQL: 자동 백업과 Point-in-Time Recovery
- Redis: 관리형 서비스 또는 HA 구성
- Object Storage: Lifecycle 기반 자동 삭제
- Jetson: 내부망, 헬스체크, 서버 추론 Fallback 검토
- 관찰성: Request ID 기반 프론트→백엔드→Jetson 로그 연결

모델 배포는 애플리케이션 배포와 분리하고 `modelVersion`을 명시합니다. 신규 모델은 Staging 평가, Canary, 전체 적용 순서로 진행하며 즉시 이전 버전으로 되돌릴 수 있어야 합니다.

## 보안과 개인정보

다시봄 스쿨은 어린이와 촬영 이미지를 다루므로 기능보다 먼저 다음 원칙을 적용합니다.

- 학생의 실명, 이메일, 전화번호와 생년월일을 요구하지 않습니다.
- 닉네임에는 금칙어와 개인정보 패턴 검사를 적용합니다.
- 촬영 화면에 얼굴이나 개인정보가 들어가지 않도록 UI에서 안내합니다.
- 가능하면 서버 수신 후 얼굴·문서 영역을 감지해 거절하거나 마스킹합니다.
- 원본 이미지는 판정에 필요한 최소 시간만 저장하고 자동 삭제합니다.
- DB에는 이미지 URL 대신 권한 없는 접근이 불가능한 Object Key를 저장합니다.
- 모든 외부 통신은 HTTPS, 내부 Jetson 통신도 토큰 또는 mTLS를 사용합니다.
- 교사 비밀번호는 Argon2id 또는 적절한 강도 설정의 bcrypt로 해시합니다.
- Access Token은 짧게, Refresh Token은 회전과 폐기를 지원합니다.
- API에 Rate Limit, 업로드 MIME/크기 검사와 악성 파일 방어를 적용합니다.
- 로그에 토큰, 비밀번호, 이미지 URL과 원본 AI 입력을 남기지 않습니다.
- 관리자 행동과 콘텐츠 변경은 감사 로그로 남깁니다.
- 개인정보 처리방침, 보호자·학교 동의, 보관 기간은 실제 적용 법률과 기관 정책 검토 후 확정합니다.

## 개발 로드맵

### 0단계 — 계약 확정

- `taxonomy.yaml`에 품목·상태·행동 코드 확정
- OpenAPI와 Jetson JSON Schema 초안 작성
- 이미지 형식, 크기, 용량, 보존 기간 합의
- 저신뢰도와 실패 코드 정의
- Mock Backend와 Mock Inference 제공

### 1단계 — 핵심 Vertical Slice

- 백엔드 학급 참여와 익명 학생 세션
- 촬영 세션 생성과 이미지 업로드
- Jetson 또는 Mock AI 작업 큐 연결
- Before 판정과 행동 안내
- After 판정과 완료 처리
- 한 품목의 XP와 카드 지급
- 프론트부터 AI까지 통합 E2E 테스트

첫 통합 대상은 현재 Mock UI와 데이터가 준비된 `투명 페트병`을 권장합니다.

### 2단계 — 학습과 보상

- 품목 확대와 도감 API
- 일일 미션, 뱃지, 캐릭터 성장
- 학급 공동 목표
- 보상 멱등성 및 통계 집계
- 세션 복구와 AI 장애 Fallback

### 3단계 — 교사 운영

- 실제 교사 인증과 학급 관리
- 익명 학생 활동, 혼동 품목과 주간 추이
- 콘텐츠 게시·초안과 충북 지역 카드
- 학급 잠금, 코드 재발급, 인증서
- 권한, 감사 로그와 운영 대시보드

### 4단계 — 운영 안정화

- Jetson 성능·온도·오프라인 모니터링
- 서버 추론 Fallback 또는 복수 장비 라우팅
- 이미지 Lifecycle과 개인정보 삭제 검증
- 부하, 장애, 보안, 실기기 테스트
- Staging 사용자 테스트와 교육 효과 측정
- Production 출시 및 모델 재학습 체계 운영

## 문서

- [전체 개발 User Flow](./다시봄스쿨_개발_Userflow.md)
- [프론트엔드 상세 README](./frontend/README.md)

백엔드와 AI 디렉터리가 생성되면 각 영역의 설치·실행·테스트·배포법은 해당 디렉터리 README에 추가하고, 공통 계약과 전체 구조는 이 문서를 기준으로 유지합니다.

## 라이선스

현재 프로젝트에는 별도의 오픈소스 라이선스가 지정되어 있지 않습니다. 외부 공개, 데이터셋 배포 또는 모델 재사용 전에 프로젝트 소유권과 라이선스 정책을 확정해야 합니다.
