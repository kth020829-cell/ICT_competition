export type Screen =
  | "welcome"
  | "join"
  | "nickname"
  | "home"
  | "camera"
  | "preview"
  | "analysis"
  | "action"
  | "after-camera"
  | "after-preview"
  | "after-analysis"
  | "reward"
  | "collection"
  | "missions"
  | "character"
  | "badges"
  | "class-goal"
  | "checklist"
  | "checklist-result"
  | "settings"
  | "teacher-login"
  | "teacher-dashboard";

export type ScanPhase = "BEFORE" | "AFTER";

// AI 서버 app/schemas/enums.py ActionCode 와 1:1로 맞춘다.
export type ActionCode =
  | "EMPTY_CONTENT"
  | "RINSE"
  | "REMOVE_LABEL"
  | "REMOVE_CAP"
  | "SEPARATE_MATERIALS"
  | "FLATTEN"
  | "CRUSH"
  | "FOLD"
  | "DISPOSE_GENERAL"
  | "ASK_ADULT";

export interface RequiredAction {
  code: ActionCode;
  labelKo: string;
  description: string;
  icon: string;
}

export interface ScanAnalysis {
  analysisId: string;
  scanSessionId: string;
  phase: ScanPhase;
  status: "ACTION_REQUIRED" | "COMPLETED";
  detection: {
    classCode: string;
    classNameKo: string;
    confidence: number;
  };
  // AI가 고른 배출처(CLEAR_PET_BIN 등). 보상 화면 안내 문구에 쓴다.
  disposalCategory?: string;
  requiredActions: RequiredAction[];
  feedback: {
    title: string;
    message: string;
    ttsText: string;
  };
}

export interface CollectionCard {
  id: string;
  name: string;
  icon: string;
  rarity: "일반" | "희귀" | "전설";
  acquired: boolean;
  hint: string;
}
