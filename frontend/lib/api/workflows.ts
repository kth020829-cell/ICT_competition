import { apiConfig } from "./config";
import { scanApi } from "./services";
import type { SessionResultResponse } from "./contracts";

export async function imageUrlToBlob(imageUrl: string) {
  if (imageUrl === "demo") {
    throw new Error("실제 API 모드에서는 카메라로 사진을 찍어주세요.");
  }
  const response = await fetch(imageUrl);
  if (!response.ok) throw new Error("촬영한 사진을 읽지 못했어요.");
  const blob = await response.blob();
  if (!blob.type.startsWith("image/")) throw new Error("이미지 파일만 사용할 수 있어요.");
  if (blob.size > 5 * 1024 * 1024) throw new Error("사진 크기는 5MB 이하여야 해요.");
  return blob;
}

const wait = () => new Promise<void>((resolve) => window.setTimeout(resolve, apiConfig.analysisPollMs));

// 백엔드는 업로드에 즉시 PROCESSING 을 돌려주고 AI 판정은 백그라운드로 돈다.
// 그래서 두 단계 모두 /sessions/{id}/result 를 폴링해서 끝날 때까지 기다린다.
async function pollUntil(
  sessionId: string,
  studentToken: string,
  done: (response: SessionResultResponse) => boolean,
) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < apiConfig.analysisTimeoutMs) {
    const response: SessionResultResponse = await scanApi.result(sessionId, studentToken);
    if (response.status === "AI_FAILED") {
      throw new Error(response.aiError ? "AI 판정에 실패했어요. 다시 찍어볼까?" : "AI 판정에 실패했어요.");
    }
    if (done(response)) return response;
    await wait();
  }
  throw new Error("AI 판정 시간이 오래 걸리고 있어요. 다시 시도해주세요.");
}

export function pollAnalysis(sessionId: string, studentToken: string) {
  return pollUntil(sessionId, studentToken, (response) => Boolean(response.result));
}

// AFTER 는 status 가 다시 ACTION_REQUIRED/COMPLETED 로 돌아오므로
// status 만으로는 이전 판정과 구분되지 않는다. after 블록이 채워졌는지로 본다.
export function pollAfterAnalysis(sessionId: string, studentToken: string) {
  return pollUntil(sessionId, studentToken, (response) => Boolean(response.after));
}
