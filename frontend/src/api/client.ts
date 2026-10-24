export class ApiError extends Error {
  code: string;
  requestId?: string;
  fields?: unknown;
  status?: number;
  constructor(
    message: string,
    code = "network_error",
    requestId?: string,
    fields?: unknown,
    status?: number,
  ) {
    super(message);
    this.code = code;
    this.requestId = requestId;
    this.fields = fields;
    this.status = status;
  }
}
export const newRequestId = () => `web-${crypto.randomUUID()}`;
export async function api<T>(
  path: string,
  init?: RequestInit,
  options?: { timeoutMs?: number; allowNull?: boolean },
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    options?.timeoutMs ?? 30_000,
  );
  try {
    const response = await fetch(`/api/v1${path}`, {
      ...init,
      signal: controller.signal,
    });
    let result;
    try {
      result = await response.json();
    } catch (error) {
      if (controller.signal.aborted) throw error;
      // A malformed error body can still report its HTTP status. It is never
      // a valid nullable success response.
      if (response.ok)
        throw new ApiError(
          "服务返回的内容无法读取，请读取最新状态后重试。",
          "invalid_response",
        );
    }
    if (!response.ok) {
      const error = result?.error;
      throw new ApiError(
        error?.message ?? "请求未完成，请核对输入或稍后重试。",
        error?.code ?? `http_${response.status}`,
        error?.request_id,
        error?.fields,
        response.status,
      );
    }
    if (result === null && !options?.allowNull)
      throw new ApiError(
        "服务返回的内容无法读取，请读取最新状态后重试。",
        "invalid_response",
      );
    return result as T;
  } catch (error) {
    if (controller.signal.aborted)
      throw new ApiError(
        "本地请求超时，已保存的结果保留。可重试原操作或读取最新状态。",
        "timeout",
      );
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "暂时无法连接本地服务。请检查服务是否运行，再重试原操作。",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}
export function post<T>(path: string, body: unknown, operatorKey?: string) {
  return api<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(operatorKey ? { "X-Operator-Key": operatorKey } : {}),
    },
    body: JSON.stringify(body),
  });
}
export const downloadUrl = (path: string) => `/api/v1${path}`;
