export interface Commit {
  sha: string;
  short_sha: string;
  author: string;
  date: string;
  subject: string;
}

export interface RepoStatus {
  initialized: boolean;
  branch: string;
  has_remote: boolean;
  pending_changes: number;
  ahead: number;
  behind: number;
  last_commit: Commit | null;
  repo_size_bytes: number;
  clean: boolean;
  activity: "idle" | "syncing" | "restoring" | "error";
  last_error: string | null;
  docker_available: boolean;
  configured: boolean;
}

export interface SubDir {
  name: string;
  rel_path: string;
  size_bytes: number;
  excluded: boolean;
}

export interface Service {
  name: string;
  rel_path: string;
  compose_file: string | null;
  size_bytes: number;
  enabled: boolean;
  subdirs: SubDir[];
}

export type SyncMode = "hybrid" | "interval" | "watch";

export interface Settings {
  services_dir: string;
  repo_url: string;
  branch: string;
  has_token: boolean;
  git_author_name: string;
  git_author_email: string;
  sync_mode: SyncMode;
  interval_seconds: number;
  debounce_seconds: number;
  auto_push: boolean;
  stop_containers_on_restore: boolean;
  notify_webhook_url: string | null;
  notify_on_success: boolean;
  notify_on_failure: boolean;
  initialized: boolean;
}

export interface LogEntry {
  ts: string;
  level: "info" | "success" | "warning" | "error";
  message: string;
}

export interface CommitFile {
  added: string;
  removed: string;
  path: string;
}
