import type { EntryFilter } from "./entries";

export type FailurePhase = "configuration" | "request" | "response";
export type FailureCategory =
  | "configuration"
  | "timeout"
  | "network"
  | "invalid_response"
  | "unexpected";

export function requestIdFrom(response: Response): string | undefined {
  const value = response.headers.get("x-request-id");
  return value && /^[\da-f-]{36}$/i.test(value) ? value : undefined;
}

export function categorizeFailure(phase: FailurePhase, error: unknown): FailureCategory {
  if (error instanceof DOMException && error.name === "TimeoutError") return "timeout";
  if (phase === "configuration") return "configuration";
  if (phase === "response") return "invalid_response";
  if (error instanceof TypeError) return "network";
  return "unexpected";
}

export function failureMessage(category: FailureCategory): string {
  if (category === "timeout") {
    return "The stories service took too long to respond. Please try again.";
  }
  if (category === "invalid_response") {
    return "The stories service returned an unexpected response. Please try again shortly.";
  }
  return "The stories service could not be reached. Please try again shortly.";
}

export function logEntriesFailure(
  filter: EntryFilter,
  category: FailureCategory | "api_error",
  requestId?: string,
  status?: number,
): void {
  console.error(JSON.stringify({
    event: "entries_fetch_failed",
    category,
    filter,
    ...(requestId === undefined ? {} : { request_id: requestId }),
    ...(status === undefined ? {} : { status_code: status }),
  }));
}
