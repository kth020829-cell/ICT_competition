"""공통 코드값 정의.

지시서 §2.2, §5.2, §5.3, §5.7 을 그대로 코드화한 것이다.
백엔드가 미션·뱃지를 판정하는 근거이므로 값 문자열을 임의로 바꾸지 않는다.
"""

from enum import Enum


class StrEnum(str, Enum):
    """JSON 직렬화 시 값 문자열로 떨어지는 문자열 Enum."""

    def __str__(self) -> str:
        return str(self.value)


# --------------------------------------------------------------------------
# YOLO 클래스 (지시서 §2.2 — 7종 고정, general_waste/etc 없음)
# --------------------------------------------------------------------------
class YoloClass(StrEnum):
    PAPER = "paper"
    PACK = "pack"
    CAN = "can"
    GLASS = "glass"
    PET = "pet"
    PLASTIC = "plastic"
    VINYL = "vinyl"


#: 학습 시 인덱스 순서. detector가 클래스 id를 문자열로 되돌릴 때 쓴다.
YOLO_CLASS_ORDER: list[str] = [
    YoloClass.PAPER,
    YoloClass.PACK,
    YoloClass.CAN,
    YoloClass.GLASS,
    YoloClass.PET,
    YoloClass.PLASTIC,
    YoloClass.VINYL,
]

CLASS_NAME_KO: dict[str, str] = {
    YoloClass.PAPER: "종이류",
    YoloClass.PACK: "종이팩",
    YoloClass.CAN: "캔류",
    YoloClass.GLASS: "유리병",
    YoloClass.PET: "페트병",
    YoloClass.PLASTIC: "플라스틱",
    YoloClass.VINYL: "비닐류",
}


# --------------------------------------------------------------------------
# 촬영 단계 / 처리 상태
# --------------------------------------------------------------------------
class Phase(StrEnum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    SINGLE = "SINGLE"  # 준비 행동이 필요 없는 품목 (건전지, 영수증 등)


class AnalysisStatus(StrEnum):
    #: 준비 행동이 남아 있다. Before 단계의 정상 응답. (지시서 §4.3)
    ACTION_REQUIRED = "ACTION_REQUIRED"
    #: 배출 준비 완료. 결론을 제시해도 되는 상태.
    COMPLETED = "COMPLETED"
    #: After — 필요한 행동을 모두 해냈다.
    IMPROVED = "IMPROVED"
    #: After — 일부만 개선됐다.
    PARTIALLY_IMPROVED = "PARTIALLY_IMPROVED"
    #: After — 개선이 확인되지 않았다.
    NOT_IMPROVED = "NOT_IMPROVED"
    #: 안전 필터 등으로 분석을 거부했다. 재촬영 유도.
    REJECTED = "REJECTED"
    #: 서버 측 실패(타임아웃·파싱 실패 등).
    FAILED = "FAILED"


# --------------------------------------------------------------------------
# 상태값 / 행동 코드 (지시서 §5.2)
# --------------------------------------------------------------------------
class StateValue(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ActionCode(StrEnum):
    EMPTY_CONTENT = "EMPTY_CONTENT"
    RINSE = "RINSE"
    REMOVE_LABEL = "REMOVE_LABEL"
    REMOVE_CAP = "REMOVE_CAP"
    SEPARATE_MATERIALS = "SEPARATE_MATERIALS"
    FLATTEN = "FLATTEN"
    CRUSH = "CRUSH"
    FOLD = "FOLD"
    DISPOSE_GENERAL = "DISPOSE_GENERAL"
    ASK_ADULT = "ASK_ADULT"


#: 아이에게 보여줄 행동 라벨. 프론트가 미션 카드에 그대로 쓴다.
ACTION_LABEL_KO: dict[str, str] = {
    ActionCode.EMPTY_CONTENT: "내용물 비우기",
    ActionCode.RINSE: "물로 헹구기",
    ActionCode.REMOVE_LABEL: "라벨 떼기",
    ActionCode.REMOVE_CAP: "뚜껑 분리하기",
    ActionCode.SEPARATE_MATERIALS: "다른 재질 분리하기",
    ActionCode.FLATTEN: "펼쳐서 말리기",
    ActionCode.CRUSH: "납작하게 누르기",
    ActionCode.FOLD: "접기",
    ActionCode.DISPOSE_GENERAL: "일반쓰레기로 버리기",
    ActionCode.ASK_ADULT: "어른과 함께 하기",
}


# --------------------------------------------------------------------------
# 배출 분류 (충북·청주 기준 — 실제 규칙은 app/rules/recycling_rules.json)
# --------------------------------------------------------------------------
class DisposalCategory(StrEnum):
    CLEAR_PET_BIN = "CLEAR_PET_BIN"
    PLASTIC_BIN = "PLASTIC_BIN"
    CAN_BIN = "CAN_BIN"
    GLASS_BIN = "GLASS_BIN"
    PAPER_PACK_BIN = "PAPER_PACK_BIN"
    PAPER_BIN = "PAPER_BIN"
    VINYL_BIN = "VINYL_BIN"
    BATTERY_BIN = "BATTERY_BIN"
    GENERAL_WASTE = "GENERAL_WASTE"


DISPOSAL_NAME_KO: dict[str, str] = {
    DisposalCategory.CLEAR_PET_BIN: "투명 페트병 전용함",
    DisposalCategory.PLASTIC_BIN: "플라스틱",
    DisposalCategory.CAN_BIN: "캔류",
    DisposalCategory.GLASS_BIN: "유리병",
    DisposalCategory.PAPER_PACK_BIN: "종이팩 전용함",
    DisposalCategory.PAPER_BIN: "종이류",
    DisposalCategory.VINYL_BIN: "비닐류",
    DisposalCategory.BATTERY_BIN: "폐건전지 전용 수거함",
    DisposalCategory.GENERAL_WASTE: "일반쓰레기",
}


# --------------------------------------------------------------------------
# 검출 출처 / 오류 코드 (지시서 §5.5, §5.7)
# --------------------------------------------------------------------------
class DetectionSource(StrEnum):
    YOLO = "yolo"
    VLM_ONLY = "vlm_only"


class ErrorCode(StrEnum):
    FACE_DETECTED = "FACE_DETECTED"
    #: 칼·주사기·깨진 유리 등. 아이에게 다시 찍게 하면 안 되는 유일한 코드다.
    DANGEROUS_OBJECT = "DANGEROUS_OBJECT"
    NOT_WASTE = "NOT_WASTE"
    MULTIPLE_OBJECTS = "MULTIPLE_OBJECTS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    IMAGE_TOO_DARK = "IMAGE_TOO_DARK"
    IMAGE_TOO_BLURRY = "IMAGE_TOO_BLURRY"
    CLASS_MISMATCH = "CLASS_MISMATCH"
    AI_TIMEOUT = "AI_TIMEOUT"
    VLM_UNAVAILABLE = "VLM_UNAVAILABLE"
    INVALID_AI_OUTPUT = "INVALID_AI_OUTPUT"
    #: 도감 28종에 없는 품목. 재촬영해도 같은 결과라 다른 물건을 권한다.
    UNSUPPORTED_CLASS = "UNSUPPORTED_CLASS"


#: 재시도 가능 여부. 지시서 §5.7 표의 "재시도" 열.
#: VLM_UNAVAILABLE 은 캐시 응답, INVALID_AI_OUTPUT 은 서버 재처리이므로
#: 아이에게 재촬영을 요구하지 않는다 → False.
ERROR_RETRYABLE: dict[str, bool] = {
    ErrorCode.FACE_DETECTED: True,
    #: 같은 물건을 다시 찍게 하면 아이가 위험물을 한 번 더 만진다.
    #: 명세서 §6 "일반 재시도 금지"가 이 뜻이다.
    ErrorCode.DANGEROUS_OBJECT: False,
    ErrorCode.NOT_WASTE: True,
    ErrorCode.MULTIPLE_OBJECTS: True,
    ErrorCode.LOW_CONFIDENCE: True,
    ErrorCode.IMAGE_TOO_DARK: True,
    ErrorCode.IMAGE_TOO_BLURRY: True,
    ErrorCode.CLASS_MISMATCH: True,
    ErrorCode.AI_TIMEOUT: True,
    ErrorCode.VLM_UNAVAILABLE: False,
    ErrorCode.INVALID_AI_OUTPUT: False,
    ErrorCode.UNSUPPORTED_CLASS: False,
}


# --------------------------------------------------------------------------
# 품목별 states 스키마 (지시서 §5.3)
# 모든 품목에 같은 키를 강제하지 않는다. 해당 없으면 not_applicable.
# --------------------------------------------------------------------------
STATE_SCHEMA: dict[str, list[str]] = {
    YoloClass.PET: ["labelAttached", "capAttached", "contentRemaining", "flattened"],
    YoloClass.PLASTIC: ["labelAttached", "contentRemaining", "contaminated"],
    YoloClass.CAN: ["contentRemaining", "contaminated", "flattened"],
    YoloClass.GLASS: ["capAttached", "contentRemaining"],
    YoloClass.PACK: ["contentRemaining", "rinsed", "unfolded"],
    YoloClass.PAPER: ["tapeAttached", "contaminated", "coated"],
    YoloClass.VINYL: ["contentRemaining", "contaminated"],
}

#: 모든 품목의 상태 키 합집합.
#:
#: VLM은 품목을 판정하기 **전에** 호출되므로 어느 스키마를 쓸지 미리 알 수 없다.
#: 그래서 요청 스키마에는 전체 키를 싣고, 응답을 받은 뒤 판정된 품목의
#: STATE_SCHEMA로 걸러낸다. 해당 없는 키는 VLM이 not_applicable로 채운다.
ALL_STATE_KEYS: list[str] = sorted({key for keys in STATE_SCHEMA.values() for key in keys})


# --------------------------------------------------------------------------
# 도감 28종 → 클래스 매핑 (지시서 §3)
# 값이 None 인 4종은 YOLO 미대응 → VLM 단독 경로.
# --------------------------------------------------------------------------
ITEM_TO_CLASS: dict[str, str | None] = {
    # pet
    "투명 페트병": YoloClass.PET,
    "플라스틱 음료병": YoloClass.PET,
    # plastic
    "배달 플라스틱 용기": YoloClass.PLASTIC,
    "칫솔": YoloClass.PLASTIC,
    "빨대": YoloClass.PLASTIC,
    "샤프심통": YoloClass.PLASTIC,
    "볼펜": YoloClass.PLASTIC,
    "페트병 뚜껑": YoloClass.PLASTIC,
    # can
    "알루미늄캔": YoloClass.CAN,
    "철캔": YoloClass.CAN,
    # glass
    "유리병": YoloClass.GLASS,
    # pack
    "우유팩": YoloClass.PACK,
    # paper
    "택배상자": YoloClass.PAPER,
    "신문지": YoloClass.PAPER,
    "공책": YoloClass.PAPER,
    "계란판": YoloClass.PAPER,
    "영수증": YoloClass.PAPER,
    "코팅지": YoloClass.PAPER,
    "스프링노트": YoloClass.PAPER,
    "컵라면 종이용기": YoloClass.PAPER,
    # vinyl
    "과자봉지": YoloClass.VINYL,
    "에어캡": YoloClass.VINYL,
    "페트병 라벨": YoloClass.VINYL,
    "아이스크림 포장지": YoloClass.VINYL,
    "오염된 비닐": YoloClass.VINYL,
    # VLM 단독 (YOLO 미대응)
    "건전지": None,
    "아이스팩": None,
    "나무젓가락": None,
    "부러진 연필": None,
}

# --------------------------------------------------------------------------
# 도감 품목 → Firestore `card` 컬렉션의 `type` (백엔드 연동)
# --------------------------------------------------------------------------
#
# 백엔드 `collect_card()` 가 `card` 에서 `type == detectedClass` 로 카드를 찾아
# 학생 도감에 등록한다. 그래서 백엔드로 나가는 detectedClass 는 YOLO 클래스가
# 아니라 **이 카드 type** 이어야 한다. 클래스(pet/can/…)를 보내면 카드가 하나도
# 안 걸린다.
#
# 값은 Firestore `card` 컬렉션 26장을 그대로 읽어 맞춘 것이다. 임의로 짓지 않는다.
ITEM_TO_CARD_TYPE: dict[str, str] = {
    # pet
    "투명 페트병": "transparency_plastic_bottle",
    "플라스틱 음료병": "plastic_bottle",
    # plastic
    "배달 플라스틱 용기": "delivery_plastic_container",
    "칫솔": "toothbrush",
    "빨대": "straw",
    "샤프심통": "pencil_lead_case",
    "볼펜": "pen",
    # can
    "알루미늄캔": "aluminum_can",
    "철캔": "iron_can",
    # pack
    "우유팩": "milk_pack",
    # paper
    "택배상자": "box",
    # 도감은 신문지와 공책을 한 장으로 묶었다. AI는 둘을 따로 판정하므로
    # 같은 카드로 보낸다.
    "신문지": "newspaper&notebook",
    "공책": "newspaper&notebook",
    "계란판": "egg_carton",
    "영수증": "receipt",
    "코팅지": "coated_paper",
    "스프링노트": "spring_notebook",
    "컵라면 종이용기": "noodle_paper_container",
    # vinyl
    "과자봉지": "snack_vinyl",
    "에어캡": "aircap",
    "페트병 라벨": "bottle_label",
    "아이스크림 포장지": "icecream_cover",
    "오염된 비닐": "contaminated_vinyl",
    # 기타 (VLM 단독)
    "건전지": "battery",
    "아이스팩": "ice_pack",
    "나무젓가락": "wood_chopstick",
    "부러진 연필": "pencil",
    # --- 아직 Firestore `card` 에 문서가 없는 품목 -------------------------
    # AI는 이 둘을 판정할 수 있는데 카드가 없다. 카드가 없으면 백엔드
    # collect_card() 가 registered=False 로 조용히 넘어가므로 판정 자체는
    # 동작하지만 도감에 등록되지 않는다. 카드를 아래 type으로 추가하면
    # 코드 수정 없이 바로 걸린다.
    "유리병": "glass_bottle",
    "페트병 뚜껑": "bottle_cap",
}

#: 아직 카드가 없는 품목. 도감 등록이 안 되므로 백엔드에 알려야 한다.
CARD_TYPES_NOT_IN_FIRESTORE: frozenset[str] = frozenset({"glass_bottle", "bottle_cap"})


#: 검출 단계를 건너뛰고 VLM에 원본을 직접 넘기는 품목.
#: 배출 결론이 상태와 무관하게 고정이라 검출이 의미 없다. (지시서 §3)
VLM_ONLY_ITEMS: frozenset[str] = frozenset(
    item for item, cls in ITEM_TO_CLASS.items() if cls is None
)
