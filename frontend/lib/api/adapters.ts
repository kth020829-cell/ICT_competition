import type { SessionResultResponse } from "./contracts";
import type { ActionCode, RequiredAction, ScanAnalysis } from "../../app/types";
import { ApiError } from "./client";

// AI 서버 ACTION_LABEL_KO 와 같은 순서·같은 문구. 아이콘만 프론트가 더한다.
const actionMetadata: Array<{
  patterns: string[];
  code: ActionCode;
  icon: string;
  label: string;
}> = [
  { patterns: ["내용물", "비우"], code: "EMPTY_CONTENT", icon: "🫗", label: "내용물 비우기" },
  { patterns: ["헹구", "rinse"], code: "RINSE", icon: "💧", label: "물로 헹구기" },
  { patterns: ["라벨", "label"], code: "REMOVE_LABEL", icon: "🏷️", label: "라벨 떼기" },
  { patterns: ["뚜껑", "캡", "cap"], code: "REMOVE_CAP", icon: "🧢", label: "뚜껑 분리하기" },
  { patterns: ["재질", "분리하기"], code: "SEPARATE_MATERIALS", icon: "✂️", label: "다른 재질 분리하기" },
  { patterns: ["펼쳐", "말리"], code: "FLATTEN", icon: "🧻", label: "펼쳐서 말리기" },
  { patterns: ["압착", "납작", "crush"], code: "CRUSH", icon: "🤏", label: "납작하게 누르기" },
  { patterns: ["접기"], code: "FOLD", icon: "📐", label: "접기" },
  { patterns: ["일반쓰레기"], code: "DISPOSE_GENERAL", icon: "🗑️", label: "일반쓰레기로 버리기" },
  { patterns: ["어른"], code: "ASK_ADULT", icon: "🧑‍🏫", label: "어른과 함께 하기" },
];

const metadataByCode = new Map(actionMetadata.map((item) => [item.code, item]));

// AI 서버 ITEM_TO_CARD_TYPE 의 역방향. detectedClass 는 도감 카드 type 이다.
// 예전 표는 5개뿐인 데다 plastic_bottle 을 "투명 페트병"으로 잘못 적어 두어,
// 대부분의 품목이 화면에 영문 코드 그대로 떴다.
const classNames: Record<string, string> = {
  aircap: "에어캡",
  aluminum_can: "알루미늄캔",
  battery: "건전지",
  bottle_cap: "페트병 뚜껑",
  bottle_label: "페트병 라벨",
  box: "택배상자",
  coated_paper: "코팅지",
  contaminated_vinyl: "오염된 비닐",
  delivery_plastic_container: "배달 플라스틱 용기",
  egg_carton: "계란판",
  glass_bottle: "유리병",
  ice_pack: "아이스팩",
  icecream_cover: "아이스크림 포장지",
  iron_can: "철캔",
  milk_pack: "우유팩",
  "newspaper&notebook": "신문지·공책",
  noodle_paper_container: "컵라면 종이용기",
  pen: "볼펜",
  pencil: "부러진 연필",
  pencil_lead_case: "샤프심통",
  plastic_bottle: "플라스틱 음료병",
  receipt: "영수증",
  snack_vinyl: "과자봉지",
  spring_notebook: "스프링노트",
  straw: "빨대",
  toothbrush: "칫솔",
  transparency_plastic_bottle: "투명 페트병",
  wood_chopstick: "나무젓가락",
};

// 받침에 따라 로/으로를 고른다. "(으)로"는 아이가 읽는 화면에 쓰기엔 거칠다.
// 한글 음절의 종성 인덱스 0(받침 없음)과 8(ㄹ)만 "로"를 쓴다.
export function withRo(word: string) {
  const last = word.trim().slice(-1);
  const code = last.charCodeAt(0);
  if (code < 0xac00 || code > 0xd7a3) return `${word}으로`;
  const jong = (code - 0xac00) % 28;
  return jong === 0 || jong === 8 ? `${word}로` : `${word}으로`;
}

// AI 서버 DISPOSAL_NAME_KO 와 같은 문구.
export const disposalNames: Record<string, string> = {
  CLEAR_PET_BIN: "투명 페트병 전용함",
  PLASTIC_BIN: "플라스틱",
  CAN_BIN: "캔류",
  GLASS_BIN: "유리병",
  PAPER_PACK_BIN: "종이팩 전용함",
  PAPER_BIN: "종이류",
  VINYL_BIN: "비닐류",
  BATTERY_BIN: "폐건전지 전용 수거함",
  GENERAL_WASTE: "일반쓰레기",
};

// actionCodes 가 있으면 그걸 쓴다. 한글 문구로 코드를 되짚는 건 마지막 수단이다.
export function toRequiredAction(action: string, code?: string): RequiredAction {
  const byCode = code ? metadataByCode.get(code as ActionCode) : undefined;
  if (byCode) {
    return { code: byCode.code, icon: byCode.icon, labelKo: action || byCode.label, description: action || byCode.label };
  }
  const normalized = action.toLowerCase();
  const found = actionMetadata.find((item) =>
    item.patterns.some((pattern) => normalized.includes(pattern)),
  );
  return {
    // 못 찾으면 임의 코드를 끼워 넣지 않는다. 예전엔 index%3 으로 돌려써서
    // 서로 다른 행동이 같은 코드를 갖고 React key 가 겹쳐 화면에서 사라졌다.
    code: found?.code ?? "ASK_ADULT",
    icon: found?.icon ?? "✨",
    labelKo: found?.label ?? action,
    description: action,
  };
}

export function toScanAnalysis(response: SessionResultResponse): ScanAnalysis {
  if (!response.result) throw new Error("아직 AI 판정 결과가 준비되지 않았어요.");
  const { result } = response;
  return {
    analysisId: `analysis-${response.sessionId}`,
    scanSessionId: response.sessionId,
    phase: "BEFORE",
    status: result.needsAction ? "ACTION_REQUIRED" : "COMPLETED",
    detection: {
      classCode: result.detectedClass,
      // 거부·실패 판정은 품목이 없다(detectedClass=""). 빈 칩을 띄우지 않는다.
      classNameKo: result.detectedClass ? (classNames[result.detectedClass] ?? result.detectedClass) : "",
      confidence: result.confidence,
    },
    disposalCategory: result.disposalCategory,
    requiredActions: result.actions.map((action, index) => toRequiredAction(action, result.actionCodes?.[index])),
    feedback: {
      // 고칠 행동이 없는데 needsAction 이면 사진 자체가 거부된 경우다.
      // (흐림·얼굴·여러 개 등) "조금만 고치면 돼!"는 그때 맞지 않는다.
      title: !result.needsAction
        ? "바로 배출해도 좋아!"
        : result.actions.length > 0
          ? "조금만 고치면 돼!"
          : "다시 찍어볼까?",
      message: result.feedbackText,
      ttsText: result.feedbackText,
    },
  };
}

export function apiErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    const messages: Record<string, string> = {
      INVALID_JOIN_CODE: "참여 코드를 다시 확인해줘.",
      CLASS_LOCKED: "지금은 새로운 학생의 참여가 잠겨 있어요.",
      IMAGE_TOO_DARK: "사진이 어두워요. 더 밝은 곳에서 다시 찍어줘.",
      MULTIPLE_OBJECTS: "물건을 한 개만 보여줘.",
      OBJECT_TOO_SMALL: "물건이 네모 안에 크게 보이도록 다시 찍어줘.",
      UNSUPPORTED_ITEM: "아직 배우지 않은 물건이에요. 다른 물건을 찍어볼까?",
      LOW_CONFIDENCE: "정확히 알아보기 어려워요. 각도를 바꿔 다시 찍어줘.",
      ANALYSIS_TIMEOUT: "판정 시간이 오래 걸리고 있어요. 다시 시도해줘.",
      DEVICE_OFFLINE: "AI 장비가 잠시 쉬고 있어요. 조금 뒤 다시 시도해줘.",
      RATE_LIMITED: "요청이 많아요. 잠시 기다렸다가 다시 해줘.",
      NETWORK_ERROR: "서버에 연결할 수 없어요. 인터넷 연결을 확인해줘.",
      REQUEST_TIMEOUT: "서버 응답이 늦어지고 있어요. 다시 시도해줘.",
      // FastAPI 검증 실패. 원문은 영어라 아이에게 그대로 보여줄 수 없다.
      HTTP_422: "입력한 내용을 다시 확인해줘.",
    };
    return messages[error.code] ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return "요청을 처리하는 중 문제가 생겼어요.";
}
