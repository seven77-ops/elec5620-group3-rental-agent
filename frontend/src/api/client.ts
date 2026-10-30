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
          "Unable to read the service response. Load the latest state and retry.",
          "invalid_response",
        );
    }
    if (!response.ok) {
      const error = result?.error;
      throw new ApiError(
        error?.message ??
          "The request could not be completed. Check your input or try again later.",
        error?.code ?? `http_${response.status}`,
        error?.request_id,
        error?.fields,
        response.status,
      );
    }
    if (result === null && !options?.allowNull)
      throw new ApiError(
        "Unable to read the service response. Load the latest state and retry.",
        "invalid_response",
      );
    return result as T;
  } catch (error) {
    if (controller.signal.aborted)
      throw new ApiError(
        "The local request timed out. Saved results are preserved. Retry the action or load the latest state.",
        "timeout",
      );
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "Unable to connect to the local service. Check that it is running and retry.",
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
