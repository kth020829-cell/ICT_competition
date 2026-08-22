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

export async function pollAnalysis(sessionId: string, studentToken: string) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < apiConfig.analysisTimeoutMs) {
    const response: SessionResultResponse = await scanApi.result(sessionId, studentToken);
    if (response.result || response.status === "ACTION_REQUIRED" || response.status === "COMPLETED") {
      return response;
    }
    await new Promise<void>((resolve) => window.setTimeout(resolve, apiConfig.analysisPollMs));
  }
  throw new Error("AI 판정 시간이 오래 걸리고 있어요. 다시 시도해주세요.");
}
