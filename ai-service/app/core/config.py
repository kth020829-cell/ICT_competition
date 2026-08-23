"""환경 설정. 값은 .env 또는 환경변수로 주입한다 (.env.example 참고)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: ai-service/ 루트
BASE_DIR = Path(__file__).resolve().parents[2]

AiMode = Literal["mock", "remote", "cached"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # --- 동작 모드 (지시서 STEP 1) ---
    #: mock   = 고정 JSON 반환. 백엔드 연동용. 모델·API 키 불필요.
    #: remote = 실제 YOLO + Claude VLM 추론.
    #: cached = 이미지 해시 캐시만 사용. 발표 데모용 오프라인 경로.
    ai_mode: AiMode = Field(default="mock", alias="AI_MODE")

    #: mock 모드에서 시나리오를 지정하지 않았을 때 쓸 기본 시나리오.
    mock_default_scenario: str = Field(
        default="pet_action_required", alias="MOCK_DEFAULT_SCENARIO"
    )

    # --- VLM (STEP 4부터 사용) ---
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    #: 지시서 §2.3은 Haiku를 기본으로 두지만, 실측에서 페트병 종류 판정이
    #: 흔들렸다. 라벨 색을 병 색으로 오인해 투명 페트병을 플라스틱 음료병으로
    #: 판정하는데, 이 둘은 뚜껑 처리가 정반대라 그대로 오안내가 된다.
    #:
    #: **더 큰 문제는 틀리면서 confidence 0.95를 보고한다는 점이다.** 신뢰도가
    #: 보정되어 있지 않아 "낮으면 승급" 전략이 성립하지 않는다.
    #: Sonnet 5는 같은 사진에서 안정적으로 맞혔다.
    #:
    #: 평가셋 110장 전량을 Sonnet으로 돌려도 약 $1이라 비용이 제약이 아니다.
    #: 근거: scripts/evaluate.py
    vlm_primary_model: str = Field(default="claude-sonnet-5", alias="VLM_PRIMARY_MODEL")
    #: 1차 모델이 실패(타임아웃·거절·연결 오류)했을 때만 쓰는 대체 모델.
    #: 오답에는 반응하지 않는다 — 오답은 예외가 아니라 정상 응답이기 때문이다.
    vlm_fallback_model: str = Field(default="claude-opus-4-8", alias="VLM_FALLBACK_MODEL")
    vlm_timeout_seconds: float = Field(default=20.0, alias="VLM_TIMEOUT_SECONDS")
    #: 판정 JSON 자체는 400토큰 남짓이지만 **thinking이 여기에 함께 계산된다.**
    #:
    #: Sonnet 5는 thinking이 기본으로 켜져 있다. 1024로 뒀더니 복잡한 사진
    #: (택배상자 등)에서 사고 도중 잘려 JSON이 끊기고 파싱이 실패했다.
    #: 실측 최대 1335토큰. 여유를 두고 4096으로 잡는다.
    #:
    #: 출력 토큰은 실제 생성분만 과금되므로 한도를 키워도 비용이 늘지 않는다.
    vlm_max_tokens: int = Field(default=4096, alias="VLM_MAX_TOKENS")
    #: 1차 모델이 실패했을 때 대체 모델로 한 번 더 시도할지. (지시서 §2.3)
    vlm_escalate_on_failure: bool = Field(default=True, alias="VLM_ESCALATE_ON_FAILURE")
    #: 사고 깊이. Sonnet 5는 기본이 high이고 thinking이 켜져 있다.
    #:
    #: 기본값 그대로 두면 **장당 15.4초**가 걸린다. 아이가 사진을 찍고 결과를
    #: 기다리는 화면에서 15초는 쓸 수 없다. low로 낮추면 5.8초로 줄고,
    #: 실측한 4장에서 판정 결과가 모두 같았다. 우리 과제는 출력 스키마가 고정된
    #: 지각·분류 문제라 깊은 추론이 크게 기여하지 않는다.
    #:
    #:   기본(thinking) 15.4s · effort=low 5.8s · thinking off 6.0s · Haiku 2.9s
    #:
    #: 정확도가 흔들리면 medium으로 올린다. 근거: scripts/evaluate.py
    vlm_effort: str = Field(default="low", alias="VLM_EFFORT")
    #: VLM에 넘기는 크롭의 긴 변 상한. 크롭은 원본보다 작지만 상한을 둬야
    #: 토큰 비용이 예측 가능해진다. 라벨 글씨가 뭉개지지 않는 선.
    vlm_max_edge: int = Field(default=768, alias="VLM_MAX_EDGE")

    # --- YOLO (STEP 2부터 사용) ---
    yolo_weights_path: Path = Field(
        default=BASE_DIR / "app" / "models" / "weights" / "dasibom_v1_best.pt",
        alias="YOLO_WEIGHTS_PATH",
    )
    #: 이 값 미만이면 크롭하지 않고 원본을 VLM에 넘긴다. (지시서 §6-6단계)
    #:
    #: 지시서는 0.35를 명시하지만 우리 촬영 조건(책상 위 근접 단독 촬영)에서
    #: 정답 클래스 conf 중앙값이 0.217이라 0.35에서는 검출률이 32.6%까지 떨어졌다.
    #: 0.15에서 76.1%. 학습 데이터(다양한 배경·거리)와의 도메인 차이로 보인다.
    #:
    #: 임계값을 낮추는 것이 설계 철학과 어긋나지 않는다. YOLO는 검출·크롭 담당이고
    #: 클래스는 힌트일 뿐이다(§1, §11-3). 이 값이 정하는 것은 "이 클래스를 믿을까"가
    #: 아니라 "크롭할 박스를 잡을까"이며, 클래스가 틀려도 VLM이 교정한다.
    #: 근거: scripts/diagnose_threshold.py
    yolo_conf_threshold: float = Field(default=0.15, alias="YOLO_CONF_THRESHOLD")
    yolo_imgsz: int = Field(default=640, alias="YOLO_IMGSZ")
    #: 2등 박스가 1등 넓이의 이 비율 이상이면 MULTIPLE_OBJECTS 후보로 본다.
    #: 개수로 세면 배경에 작게 걸린 물체 때문에 정상 사진이 계속 반려된다.
    multiple_object_area_ratio: float = Field(default=0.5, alias="MULTIPLE_OBJECT_AREA_RATIO")
    #: 다만 1등 박스와 이 비율 이상 겹치면 **같은 물체**로 본다.
    #:
    #: 크기 조건만으로는 부족했다. YOLO가 한 물체를 여러 박스로 쪼갠다 —
    #: 캔 몸통과 뚜껑처럼 포개지기도 하고, 큰 종이(포스터·영수증)는 가로 띠로
    #: 갈라진다. 평가셋은 전부 단일 물체인데 반려가 났다.
    #:
    #: 임계값별 오탐률 (검출된 48장 기준):
    #:   0.5 → 16.7% · 0.2 → 8.3% · **0.1 → 4.2%** · 0.05 이하 → 개선 없음
    #:
    #: 0.1이 무릎점이다. 남은 4.2%는 박스가 완전히 떨어져 잡힌 경우라 겹침으로는
    #: 풀 수 없다. 두 물체가 살짝 겹쳐 놓인 사진을 놓칠 수 있지만, 그때는 큰 쪽
    #: 하나를 판정해 준다. 정상 사진을 반려하는 쪽이 더 나쁘다. (지시서 §4.1)
    multiple_object_overlap_ratio: float = Field(
        default=0.1, alias="MULTIPLE_OBJECT_OVERLAP_RATIO"
    )

    # --- 안전 필터 (STEP 3) ---
    #: MediaPipe BlazeFace(short-range) 가중치. 224KB라 저장소에 함께 둔다.
    face_model_path: Path = Field(
        default=BASE_DIR / "app" / "models" / "weights" / "blaze_face_short_range.tflite",
        alias="FACE_MODEL_PATH",
    )
    #: 얼굴 검출 임계값.
    #:
    #: BlazeFace가 **캔 뚜껑을 얼굴로 오인한다.** 원형 테두리 안에 따개와
    #: 각인이 배치된 모양이 눈·코·입 배치와 닮은 탓으로 보인다. 건전지 상단도
    #: 같은 이유로 걸린다.
    #:
    #: 평가셋 62장(전부 물건 사진이므로 검출은 모두 오탐)에서 잰 오탐률:
    #:
    #:   0.4 → 21.0% · 0.5 → 9.7% · 0.6 → 3.2% · **0.7 → 0.0%**
    #:
    #: 관측된 최대 오탐 점수는 0.622(`c2 (1).jpg`)다.
    #:
    #: 진짜 얼굴로도 검증했다. MediaPipe 공개 테스트 인물 사진 2장을 실제 전처리에
    #: 태워 쟀다(팀원 얼굴을 찍지 않았다 — 그 자체로 개인정보가 하나 늘어난다):
    #:
    #:   화면을 채우는 얼굴  0.832 ~ 0.983   ← 반드시 걸러야 하는 경우
    #:   물건 사진 62장 최대 0.622          ← 걸러선 안 되는 경우
    #:
    #: 두 분포가 겹치지 않고 0.7이 그 사이에 있다. 양쪽으로 여유가 있다.
    #:
    #: ⚠️ **작게 찍힌 얼굴은 잡지 못한다.** 같은 사진을 축소해 넣으면 0.07~0.31이
    #: 나온다. 이건 임계값 문제가 아니라 모델 특성이다(short-range). 그 점수대는
    #: 캔 뚜껑 오탐(0.622)보다 낮아서, 임계값을 아무리 낮춰도 먼 얼굴만 골라
    #: 잡을 수는 없다. 배경의 작은 얼굴은 크롭에서 잘려 나가므로 크롭 경로에서는
    #: 문제가 없지만, 검출 실패로 원본이 통째로 넘어가는 폴백 경로(약 20%)에는
    #: 남는 위험이다. 없애려면 full-range 모델로 바꿔야 한다.
    face_min_confidence: float = Field(default=0.7, alias="FACE_MIN_CONFIDENCE")

    # --- 전처리 (STEP 2) ---
    #: 클라이언트가 긴 변 1024px로 리사이즈해 올린다. (지시서 §10)
    #: 평가도 같은 조건이어야 숫자가 실제 서비스와 맞는다.
    client_max_edge: int = Field(default=1024, alias="CLIENT_MAX_EDGE")
    #: 라플라시안 분산. 이 값 미만이면 IMAGE_TOO_BLURRY.
    #: 평가셋 실측으로 정했다. 60이면 경계선 사진(45·51)까지 반려해 46장 중 3장을
    #: 잃는다. 40이면 실제로 흔들린 1장만 걸러진다. 결벽하게 굴면 제대로 찍은 것도
    #: 반려되어 아이가 이탈한다는 §4.1의 판단 기준을 품질 검사에도 적용했다.
    min_blur_score: float = Field(default=40.0, alias="MIN_BLUR_SCORE")
    #: 그레이스케일 평균 밝기(0~255). 이 값 미만이면 IMAGE_TOO_DARK.
    min_brightness: float = Field(default=40.0, alias="MIN_BRIGHTNESS")
    #: 크롭 여백 비율. 라벨 가장자리나 뚜껑이 잘리면 VLM이 판정할 대상을 잃는다.
    crop_padding: float = Field(default=0.08, alias="CROP_PADDING")

    # --- 배출 기준 ---
    # --- 캐시 (STEP 9) ---
    #: 판정 결과 보관 위치. 이미지는 저장하지 않고 해시와 판정 JSON만 남는다.
    #: .gitignore 로 제외되어 있다. 항목 하나가 1~2KB라 수천 장이어도 몇 MB다.
    cache_dir: Path = Field(default=BASE_DIR / "app" / "cache", alias="CACHE_DIR")
    #: remote 모드에서 캐시를 쓸지. 끄면 매번 VLM을 부른다(프롬프트 실험용).
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")

    # --- 배출 기준 ---
    default_region_code: str = Field(default="KR-43-CHEONGJU", alias="DEFAULT_REGION_CODE")
    rules_path: Path = Field(
        default=BASE_DIR / "app" / "rules" / "recycling_rules.json", alias="RULES_PATH"
    )
    prompts_dir: Path = Field(default=BASE_DIR / "app" / "prompts", alias="PROMPTS_DIR")

    # --- 버전 태그 (응답 processing 블록에 그대로 실린다) ---
    model_version: str = Field(default="yolo11n-dasibom-1.0.0", alias="MODEL_VERSION")
    prompt_version: str = Field(default="child-feedback-0.1.0", alias="PROMPT_VERSION")
    rule_version: str = Field(default="recycling-rules-2026-01", alias="RULE_VERSION")

    # --- 서버 ---
    cors_allow_origins: str = Field(default="*", alias="CORS_ALLOW_ORIGINS")
    #: 기동 시 모델을 미리 로드한다. 끄면 첫 요청이 4~5초 걸린다.
    warmup_on_startup: bool = Field(default=True, alias="WARMUP_ON_STARTUP")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
