export interface HostError {
  code?: string | number;
  message?: string;
  details?: unknown;
}

export interface HostEnvelope<T> {
  ok: boolean;
  result?: T;
  error?: HostError;
}

export interface StorageGetResult<T = unknown> {
  value: T | null;
  exists?: boolean;
  etag?: string;
  generation?: number;
}

export interface StorageSetResult {
  etag?: string;
  generation?: number;
  size_bytes?: number;
}

export interface AnnaRuntime {
  runtimeState?: Record<string, unknown>;
  storage: {
    get(args: {
      key: string;
      scope?: "app" | "user" | "tool";
    }): Promise<StorageGetResult | HostEnvelope<StorageGetResult>>;
    set(args: {
      key: string;
      value: unknown;
      scope?: "app" | "user" | "tool";
      if_match?: string;
    }): Promise<StorageSetResult | HostEnvelope<StorageSetResult>>;
  };
  tools: {
    invoke(args: {
      tool_id: string;
      method?: string;
      args?: Record<string, unknown>;
      timeoutMs?: number;
    }): Promise<unknown>;
  };
}

interface AnnaRuntimeModule {
  AnnaAppRuntime: {
    connect(): Promise<AnnaRuntime>;
  };
}

const SDK_URL = "/static/anna-apps/_sdk/latest/index.js";
let runtimePromise: Promise<AnnaRuntime> | undefined;

export function connectAnna(): Promise<AnnaRuntime> {
  runtimePromise ??= import(/* @vite-ignore */ SDK_URL).then(
    (module: AnnaRuntimeModule) => module.AnnaAppRuntime.connect(),
  );
  return runtimePromise;
}

function isEnvelope(value: unknown): value is HostEnvelope<unknown> {
  return Boolean(
    value &&
      typeof value === "object" &&
      "ok" in value &&
      typeof (value as { ok: unknown }).ok === "boolean",
  );
}

export function unwrapHostResult<T>(value: T | HostEnvelope<T>): T {
  if (!isEnvelope(value)) {
    return value;
  }

  if (!value.ok) {
    const code = value.error?.code;
    const message = value.error?.message ?? "Anna host request failed";
    throw new Error(code ? `[${code}] ${message}` : message);
  }

  return value.result as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (
    error &&
    typeof error === "object" &&
    "message" in error &&
    typeof error.message === "string"
  ) {
    return error.message;
  }
  return "Something went wrong";
}
