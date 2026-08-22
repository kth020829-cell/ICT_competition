import { apiConfig } from "./config";

export interface ApiErrorBody {
  success?: false;
  message?: string;
  detail?: string;
  code?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly retryable: boolean,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | Record<string, unknown> | null;
  studentToken?: string;
  teacherId?: string;
  timeoutMs?: number;
}

const isBodyInit = (body: unknown): body is BodyInit =>
  typeof body === "string" ||
  body instanceof Blob ||
  body instanceof FormData ||
  body instanceof URLSearchParams ||
  body instanceof ArrayBuffer;

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? apiConfig.requestTimeoutMs,
  );
  const headers = new Headers(options.headers);
  if (options.studentToken) headers.set("student-token", options.studentToken);
  if (options.teacherId) headers.set("teacher_id", options.teacherId);

  let body = options.body;
  if (body != null && !isBodyInit(body)) {
    headers.set("content-type", "application/json");
    body = JSON.stringify(body);
  }

  try {
    const response = await fetch(`${apiConfig.baseUrl}${path}`, {
      ...options,
      body: body as BodyInit | null | undefined,
      headers,
      signal: controller.signal,
    });
    const contentType = response.headers.get("content-type") ?? "";
    const payload: unknown = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      const error = typeof payload === "object" && payload !== null ? payload as ApiErrorBody : {};
      throw new ApiError(
        error.message ?? error.detail ?? "요청을 처리하지 못했어요.",
        response.status,
        error.code ?? `HTTP_${response.status}`,
        response.status === 408 || response.status === 429 || response.status >= 500,
      );
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("서버 응답이 늦어지고 있어요.", 408, "REQUEST_TIMEOUT", true);
    }
    throw new ApiError("서버에 연결할 수 없어요.", 0, "NETWORK_ERROR", true);
  } finally {
    window.clearTimeout(timeout);
  }
}
