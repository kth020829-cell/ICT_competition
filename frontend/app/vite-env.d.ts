/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_APP_MODE?: "development" | "staging" | "production";
  readonly VITE_ENABLE_MOCK?: string;
  readonly VITE_API_TIMEOUT_MS?: string;
  readonly VITE_ANALYSIS_POLL_MS?: string;
  readonly VITE_ANALYSIS_TIMEOUT_MS?: string;
  readonly VITE_TEACHER_CLASS_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
