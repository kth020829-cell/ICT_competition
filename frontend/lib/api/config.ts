const numberFromEnv = (value: string | undefined, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

export const apiConfig = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, ""),
  appMode: import.meta.env.VITE_APP_MODE ?? "development",
  enableMock: (import.meta.env.VITE_ENABLE_MOCK ?? "true").toLowerCase() === "true",
  requestTimeoutMs: numberFromEnv(import.meta.env.VITE_API_TIMEOUT_MS, 15_000),
  analysisPollMs: numberFromEnv(import.meta.env.VITE_ANALYSIS_POLL_MS, 1_200),
  analysisTimeoutMs: numberFromEnv(import.meta.env.VITE_ANALYSIS_TIMEOUT_MS, 30_000),
  teacherClassId: import.meta.env.VITE_TEACHER_CLASS_ID ?? "3dOB9YRWE1ItMmpdhyPa",
} as const;
