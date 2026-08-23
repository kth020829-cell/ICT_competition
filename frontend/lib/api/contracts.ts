export type SessionType = "FREE" | "MISSION";
export type SessionStatus = "CREATED" | "PROCESSING" | "ACTION_REQUIRED" | "COMPLETED";

export interface StudentAuthResponse {
  success: true;
  studentId: string;
  studentToken: string;
  nickname: string;
  classId: string;
}

export interface HomeResponse {
  student: { nickname: string; level: number; xp: number; nextLevelXp: number };
  classGoal: { current: number; target: number };
  collection: { collected: number; total: number };
}

export interface ScanSessionResponse {
  success: true;
  sessionId: string;
  type: SessionType;
  status: SessionStatus;
}

export interface UploadResponse {
  success: true;
  sessionId: string;
  status: SessionStatus;
  message: string;
}

export interface SessionResultResponse {
  success: true;
  sessionId: string;
  status: SessionStatus | "AI_FAILED";
  result?: {
    detectedClass: string;
    confidence: number;
    needsAction: boolean;
    actions: string[];
    // AI 서버가 주는 안정적인 행동 코드. actions 와 같은 순서·같은 길이.
    actionCodes?: string[];
    disposalCategory: string;
    feedbackText: string;
    analysisId?: string;
  };
  // AFTER 판정 결과. 백엔드가 AI 비교를 끝내면 채워진다.
  after?: { improved: boolean; remainingActions: string[] };
  aiError?: string | null;
}

export interface AfterResponse {
  success: true;
  sessionId: string;
  status: "ACTION_REQUIRED" | "COMPLETED";
  improved: boolean;
  remainingActions: string[];
  message: string;
}

export interface RewardResponse {
  success: true;
  sessionId: string;
  rewardTransactionId: string;
  reward: { xp: number; missionCompleted: boolean };
  student: { xp: number; level: number; badge: string };
  // 도감에 카드가 없는 품목이면 registered=false 로 온다. cardId 도 없다.
  collection: { registered: boolean; cardId?: string; isNew?: boolean; count?: number };
}

export interface CollectionItemResponse {
  cardId: string;
  name: string;
  type: string;
  level: number;
  class: string;
  needsActions?: string[] | null;
  collected: boolean;
  count: number;
  message?: string;
}

export interface CollectionResponse {
  success: true;
  studentId: string;
  totalCount: number;
  collectedCount: number;
  collections: CollectionItemResponse[];
}

export interface Mission {
  missionId: string;
  title: string;
  type: string;
  rewardXp: number;
  active: boolean;
  description: string;
  condition: Array<Record<string, number>>;
}

export interface MissionResponse {
  success: true;
  date?: string;
  mission: Mission;
}

export interface MissionCompleteResponse {
  success: true;
  alreadyCompleted: boolean;
  missionId: string;
  sessionId: string;
  completed: boolean;
  bonusXp: number;
  message: string;
}

export interface TeacherAuthResponse {
  success: true;
  teacherId: string;
  name: string;
  email: string;
}

export interface TeacherClassResponse {
  success: true;
  classId: string;
  classCode: string;
  className: number;
  grade: number;
  school: string;
  goalCurrent?: number;
  goalTarget?: number;
  locked?: boolean;
  studentCount?: number;
}

export interface ClassCodeResponse {
  success: true;
  classCode: string;
  locked: boolean;
}

export interface ClassLockResponse {
  success: true;
  classId: string;
  locked: boolean;
}

export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function assertApiSuccess<T extends { success: true }>(
  value: unknown,
  requiredKeys: string[],
  label: string,
): asserts value is T {
  if (!isRecord(value) || value.success !== true || requiredKeys.some((key) => !(key in value))) {
    throw new Error(`${label} 응답 형식이 올바르지 않습니다.`);
  }
}
