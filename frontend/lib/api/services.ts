import { apiRequest } from "./client";
import {
  assertApiSuccess,
  type AfterResponse,
  type ClassCodeResponse,
  type ClassLockResponse,
  type CollectionItemResponse,
  type CollectionResponse,
  type HomeResponse,
  type MissionCompleteResponse,
  type MissionResponse,
  type RewardResponse,
  type ScanSessionResponse,
  type SessionResultResponse,
  type SessionType,
  type StudentAuthResponse,
  type TeacherAuthResponse,
  type TeacherClassResponse,
  type UploadResponse,
} from "./contracts";

async function checked<T extends { success: true }>(
  request: Promise<unknown>,
  keys: string[],
  label: string,
) {
  const value = await request;
  assertApiSuccess<T>(value, keys, label);
  return value;
}

export const studentApi = {
  enter: (classCode: string, nickname: string) => checked<StudentAuthResponse>(
    apiRequest("/auth/student", { method: "POST", body: { classCode, nickname } }),
    ["studentId", "studentToken", "nickname", "classId"],
    "학생 인증",
  ),
  home: (studentToken: string) => apiRequest<HomeResponse>("/home", { studentToken }),
};

export const scanApi = {
  create: (studentToken: string, type: SessionType = "FREE") => checked<ScanSessionResponse>(
    apiRequest("/sessions", { method: "POST", studentToken, body: { type } }),
    ["sessionId", "type", "status"],
    "촬영 세션",
  ),
  uploadBefore: (sessionId: string, studentToken: string, image: Blob) => checked<UploadResponse>(
    apiRequest(`/sessions/${encodeURIComponent(sessionId)}/before`, {
      method: "POST",
      studentToken,
      headers: { "content-type": image.type || "image/jpeg" },
      body: image,
    }),
    ["sessionId", "status", "message"],
    "1차 촬영",
  ),
  uploadAfter: (sessionId: string, studentToken: string, improved = true) => checked<AfterResponse>(
    apiRequest(`/sessions/${encodeURIComponent(sessionId)}/after`, {
      method: "POST",
      studentToken,
      body: { improved },
    }),
    ["sessionId", "status", "improved", "remainingActions", "message"],
    "재촬영",
  ),
  result: (sessionId: string, studentToken: string) => checked<SessionResultResponse>(
    apiRequest(`/sessions/${encodeURIComponent(sessionId)}/result`, { studentToken }),
    ["sessionId", "status"],
    "판정 결과",
  ),
  reward: (sessionId: string, studentToken: string) => checked<RewardResponse>(
    apiRequest(`/sessions/${encodeURIComponent(sessionId)}/reward`, { method: "POST", studentToken }),
    ["sessionId", "rewardTransactionId", "reward", "student", "collection"],
    "보상",
  ),
};

export const collectionApi = {
  list: (studentToken: string) => checked<CollectionResponse>(
    apiRequest("/collection", { studentToken }),
    ["studentId", "totalCount", "collectedCount", "collections"],
    "도감 목록",
  ),
  detail: (cardId: string, studentToken: string) => checked<CollectionItemResponse & { success: true }>(
    apiRequest(`/collection/${encodeURIComponent(cardId)}`, { studentToken }),
    ["cardId", "name", "type", "class", "level", "collected", "count"],
    "도감 상세",
  ),
};

export const missionApi = {
  today: (studentToken: string) => checked<MissionResponse>(
    apiRequest("/missions/today", { studentToken }),
    ["mission"],
    "오늘의 미션",
  ),
  detail: (missionId: string, studentToken: string) => checked<MissionResponse>(
    apiRequest(`/missions/${encodeURIComponent(missionId)}`, { studentToken }),
    ["mission"],
    "미션 상세",
  ),
  complete: (missionId: string, sessionId: string, studentToken: string) => checked<MissionCompleteResponse>(
    apiRequest(`/missions/${encodeURIComponent(missionId)}/complete?session_id=${encodeURIComponent(sessionId)}`, {
      method: "POST",
      studentToken,
    }),
    ["missionId", "sessionId", "completed", "bonusXp", "message"],
    "미션 완료",
  ),
};

export const teacherApi = {
  login: (name: string, email: string) => checked<TeacherAuthResponse>(
    apiRequest("/teacher", { method: "POST", body: { name, email } }),
    ["teacherId", "name", "email"],
    "교사 로그인",
  ),
  createClass: (
    teacherId: string,
    input: { school: string; grade: number; className: number; goalTarget: number },
  ) => checked<TeacherClassResponse>(
    apiRequest("/teacher/classes", { method: "POST", teacherId, body: input }),
    ["classId", "classCode", "className", "grade", "school"],
    "학급 생성",
  ),
  classDashboard: (teacherId: string, classId: string) => checked<TeacherClassResponse>(
    apiRequest(`/teacher/classes/${encodeURIComponent(classId)}`, { teacherId }),
    ["classId", "classCode", "className", "grade", "school"],
    "학급 현황",
  ),
  classCode: (teacherId: string, classId: string) => checked<ClassCodeResponse>(
    apiRequest(`/teacher/classes/${encodeURIComponent(classId)}/code`, { teacherId }),
    ["classCode", "locked"],
    "학급 코드",
  ),
  setLocked: (teacherId: string, classId: string, locked: boolean) => checked<ClassLockResponse>(
    apiRequest(`/teacher/classes/${encodeURIComponent(classId)}/lock`, {
      method: "PATCH",
      teacherId,
      body: { locked },
    }),
    ["classId", "locked"],
    "학급 잠금",
  ),
};
