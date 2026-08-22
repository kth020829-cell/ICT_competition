import type { SessionResultResponse } from "./contracts";
import type { ActionCode, RequiredAction, ScanAnalysis } from "../../app/types";
import { ApiError } from "./client";

const actionMetadata: Array<{
  patterns: string[];
  code: ActionCode;
  icon: string;
  label: string;
}> = [
  { patterns: ["라벨", "label"], code: "REMOVE_LABEL", icon: "🏷️", label: "라벨 떼기" },
  { patterns: ["뚜껑", "캡", "cap"], code: "REMOVE_CAP", icon: "🧢", label: "뚜껑 분리하기" },
  { patterns: ["압착", "납작", "crush"], code: "CRUSH", icon: "🤏", label: "납작하게 누르기" },
];

const classNames: Record<string, string> = {
  plastic_bottle: "투명 페트병",
  transparency_plastic_bottle: "투명 페트병",
  pet_transparent: "투명 페트병",
  paper_box: "종이 상자",
  beverage_can: "음료 캔",
};

function toAction(action: string, index: number): RequiredAction {
  const normalized = action.toLowerCase();
  const found = actionMetadata.find((item) =>
    item.patterns.some((pattern) => normalized.includes(pattern)),
  );
  return {
    code: found?.code ?? (["REMOVE_LABEL", "REMOVE_CAP", "CRUSH"] as const)[index % 3],
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
      classNameKo: classNames[result.detectedClass] ?? result.detectedClass,
      confidence: result.confidence,
    },
    requiredActions: result.actions.map(toAction),
    feedback: {
      title: result.needsAction ? "조금만 고치면 돼!" : "바로 배출해도 좋아!",
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
    };
    return messages[error.code] ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return "요청을 처리하는 중 문제가 생겼어요.";
}
