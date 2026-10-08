import axios, { AxiosError, type AxiosRequestConfig } from "axios";

/**
 * One axios instance for the whole app.
 *
 * Auth is cookie-based (httpOnly access + refresh tokens), so no token is ever
 * held in JavaScript. Two things the client must do itself:
 *
 *  1. CSRF — the backend uses the double-submit pattern: every mutating request
 *     must echo the JS-readable `csrf_token` cookie in `X-CSRF-Token`.
 *  2. Refresh — access tokens live 15 minutes. On a 401 the client calls
 *     `/v1/auth/refresh` once (shared by concurrent requests) and retries.
 */
export const api = axios.create({
  baseURL: "/v1",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

function readCookie(name: string): string | null {
  const match = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

const SAFE_METHODS = new Set(["get", "head", "options"]);

api.interceptors.request.use((config) => {
  const method = (config.method ?? "get").toLowerCase();
  if (!SAFE_METHODS.has(method)) {
    const csrf = readCookie("csrf_token");
    if (csrf) config.headers.set("X-CSRF-Token", csrf);
  }
  return config;
});

// Endpoints where a 401 is the answer itself, not an expired session.
const NO_REFRESH = [
  "/auth/login",
  "/auth/login/mfa",
  "/auth/register",
  "/auth/refresh",
  "/auth/logout",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/change-password",
  "/auth/mfa/disable",
];

let refreshing: Promise<boolean> | null = null;

export function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = axios
      .post("/v1/auth/refresh", null, { withCredentials: true })
      .then(() => true)
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

type RetriableConfig = AxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const url = config?.url ?? "";
    if (
      error.response?.status === 401 &&
      config &&
      !config._retried &&
      !NO_REFRESH.some((path) => url.startsWith(path))
    ) {
      config._retried = true;
      if (await refreshSession()) return api(config);
    }
    return Promise.reject(error);
  },
);

export interface ApiErrorBody {
  error?: string;
  message?: string;
  details?: { field?: string; message?: string; loc?: unknown[]; msg?: string }[];
  [key: string]: unknown;
}

/** The error body, for codes that carry extra fields (e.g. ACCOUNT_DELETED's purge_after). */
export function apiErrorBody(err: unknown): ApiErrorBody | undefined {
  return axios.isAxiosError(err) ? (err.response?.data as ApiErrorBody | undefined) : undefined;
}

export function apiErrorCode(err: unknown): string | undefined {
  if (axios.isAxiosError(err)) {
    return (err.response?.data as ApiErrorBody | undefined)?.error;
  }
  return undefined;
}

/** A sentence a person can read, whatever shape the failure took. */
export function errorMessage(err: unknown, fallback = "Something went wrong. Try again."): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return "Can't reach the server. Check that the backend is running.";
    const body = err.response.data as ApiErrorBody | undefined;
    if (err.response.status === 429) return "Too many attempts. Wait a minute and try again.";
    if (body?.details?.length) {
      const first = body.details[0];
      return first.message ?? first.msg ?? body.message ?? fallback;
    }
    if (body?.message) return body.message;
  }
  return fallback;
}
