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

export type ActionCode = "REMOVE_LABEL" | "REMOVE_CAP" | "CRUSH";

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
