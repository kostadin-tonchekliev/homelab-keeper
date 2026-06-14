import type {
  Commit,
  CommitFile,
  LogEntry,
  RepoStatus,
  Service,
  Settings,
} from "./types";

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  status: () => req<RepoStatus>("/api/status"),
  backup: (message?: string) =>
    req<{ ok: boolean; changed?: boolean; commit?: string }>("/api/backup", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  push: () => req<{ ok: boolean }>("/api/push", { method: "POST" }),
  unlock: () => req<{ ok: boolean; removed: string[] }>("/api/unlock", { method: "POST" }),
  fetch: () => req<{ ok: boolean }>("/api/fetch", { method: "POST" }),
  history: (limit = 100) => req<Commit[]>(`/api/history?limit=${limit}`),
  commitDetail: (sha: string) =>
    req<{ files: CommitFile[] }>(`/api/history/${sha}`),
  diff: (sha: string, path?: string) =>
    req<{ diff: string }>(
      `/api/diff/${sha}${path ? `?path=${encodeURIComponent(path)}` : ""}`,
    ),
  services: () => req<Service[]>("/api/services"),
  toggleService: (name: string, enabled: boolean) =>
    req("/api/services/toggle", {
      method: "POST",
      body: JSON.stringify({ name, enabled }),
    }),
  toggleExclude: (path: string, enabled: boolean) =>
    req("/api/excludes/toggle", {
      method: "POST",
      body: JSON.stringify({ path, enabled }),
    }),
  settings: () => req<Settings>("/api/settings"),
  updateSettings: (body: Partial<Settings> & { github_token?: string }) =>
    req<Settings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  init: () => req<{ ok: boolean }>("/api/init", { method: "POST" }),
  restorePreview: (sha: string, paths: string[]) =>
    req<{ diff: string }>("/api/restore/preview", {
      method: "POST",
      body: JSON.stringify({ sha, paths }),
    }),
  restore: (sha: string, paths: string[]) =>
    req<{ ok: boolean; restarted?: string[] }>("/api/restore", {
      method: "POST",
      body: JSON.stringify({ sha, paths }),
    }),
  logs: (limit = 200) => req<LogEntry[]>(`/api/logs?limit=${limit}`),
};
