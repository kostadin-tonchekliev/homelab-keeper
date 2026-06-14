import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { formatBytes, formatDate, timeAgo } from "../lib/format";
import type { LogEntry, RepoStatus } from "../types";

// ---- Step detection logic --------------------------------------------------
// Steps transition by matching log messages emitted by the backend at the
// START of each operation (so the UI advances as each phase begins, not after
// it finishes — which could take a long time for large repos).
const BACKUP_STEPS = [
  { id: "staging",    label: "Staging changed files" },
  { id: "committing", label: "Creating commit"        },
  { id: "pushing",    label: "Pushing to GitHub"      },
] as const;

type StepId = (typeof BACKUP_STEPS)[number]["id"];

function detectStep(logs: LogEntry[]): { activeStep: StepId; doneUpTo: number; detail: string } {
  const recent = logs.slice(0, 40); // logs come back newest-first

  const hasPushed    = recent.some((l) => /Pushed to origin/i.test(l.message));
  const hasCommitted = recent.some((l) => /Committed backup/i.test(l.message));
  // "Staging complete: N file(s) changed. Creating commit…" signals staging is done.
  const stagingDone  = recent.some((l) => /Staging complete.*Creating commit/i.test(l.message));
  const stagingMsg   = recent.find((l) => /Staging/i.test(l.message))?.message
                       ?? "Running git add -A… (this can take a while for large directories)";

  if (hasPushed)    return { activeStep: "pushing",    doneUpTo: 3, detail: recent.find((l) => /Pushed to origin/i.test(l.message))?.message ?? "" };
  if (hasCommitted) return { activeStep: "pushing",    doneUpTo: 2, detail: "Pushing commits to remote…" };
  if (stagingDone)  return { activeStep: "committing", doneUpTo: 1, detail: "Running git commit…" };
  return                    { activeStep: "staging",    doneUpTo: 0, detail: stagingMsg };
}

// ---- Progress panel --------------------------------------------------------
function BackupProgress({ logs }: { logs: LogEntry[] }) {
  const { activeStep, doneUpTo, detail } = detectStep(logs);
  const activeIdx = BACKUP_STEPS.findIndex((s) => s.id === activeStep);

  const barPct = Math.round((doneUpTo / BACKUP_STEPS.length) * 100);
  const isIndeterminate = doneUpTo === 0 && logs.length === 0;

  return (
    <div className="card" style={{ marginBottom: 20, borderColor: "var(--accent)" }}>
      <div className="row between" style={{ marginBottom: 14 }}>
        <strong style={{ fontSize: 14 }}>Backup in progress…</strong>
        <span className="muted" style={{ fontSize: 12 }}>Do not navigate away</span>
      </div>

      <div className="progress-bar-track">
        <div
          className={`progress-bar-fill${isIndeterminate ? " indeterminate" : ""}`}
          style={{ width: `${Math.max(barPct, 6)}%` }}
        />
      </div>

      <div className="steps">
        {BACKUP_STEPS.map((s, i) => {
          const state =
            i < activeIdx ? "done"
            : i === activeIdx ? "active"
            : "pending";
          return (
            <div key={s.id}>
              <div className={`step ${state}`}>
                <div className="step-icon">
                  {state === "done" ? "✓" : i + 1}
                </div>
                <span className="step-label">{s.label}</span>
              </div>
              {state === "active" && detail && (
                <div className="step-detail">{detail}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---- Dashboard -------------------------------------------------------------
export function Dashboard() {
  const [status, setStatus] = useState<RepoStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [backupLogs, setBackupLogs] = useState<LogEntry[]>([]);
  const pollRef = useRef<number | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      setStatus(await api.status());
      setLoadError(null);
    } catch (e) {
      setStatus((prev) => {
        if (prev === null) setLoadError(String((e as Error).message));
        return prev;
      });
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 5000);
    return () => window.clearInterval(id);
  }, [load]);

  const startLogPolling = () => {
    // Capture a timestamp so we only show logs from this backup run.
    const startTime = new Date().toISOString();
    pollRef.current = window.setInterval(async () => {
      try {
        const all = await api.logs(60);
        // Keep only log lines that arrived after the backup started.
        setBackupLogs(all.filter((l) => l.ts >= startTime));
      } catch {
        // ignore polling errors
      }
    }, 800);
  };

  const stopLogPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const doBackup = async () => {
    setBusy(true);
    setBackupLogs([]);
    startLogPolling();
    try {
      const res = await api.backup();
      toast(
        res.changed ? `Backup committed (${res.commit})` : "No changes to back up",
        "success",
      );
      await load();
    } catch (e) {
      toast(String((e as Error).message), "error");
    } finally {
      stopLogPolling();
      setBusy(false);
      setBackupLogs([]);
    }
  };

  const doPush = async () => {
    setBusy(true);
    try {
      await api.push();
      toast("Pushed to remote", "success");
      await load();
    } catch (e) {
      toast(String((e as Error).message), "error");
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return (
      <div className="empty">
        {loadError ? (
          <>
            <div className="red" style={{ marginBottom: 8 }}>Could not reach the backend</div>
            <div className="mono muted">{loadError}</div>
            <button className="btn secondary" style={{ marginTop: 16 }} onClick={load}>
              Retry
            </button>
          </>
        ) : (
          "Loading…"
        )}
      </div>
    );
  }

  if (!status.configured) {
    return (
      <>
        <h1 className="page-title">Dashboard</h1>
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Not configured</h3>
          <p className="muted">
            Connect a private GitHub repository to start backing up your
            services.
          </p>
          <Link to="/settings" className="btn">
            Go to Settings
          </Link>
        </div>
      </>
    );
  }

  const activity = status.activity;

  return (
    <>
      <div className="row between">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">
            Branch <span className="mono">{status.branch}</span>
          </p>
        </div>
        <span className={`badge ${activity}`}>
          <span className="dot" />
          {activity}
        </span>
      </div>

      {status.last_error && (
        <div className="card" style={{ borderColor: "var(--red)", marginBottom: 16 }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <h3 className="red" style={{ margin: 0 }}>Last error</h3>
            {status.last_error.includes("index.lock") && (
              <button
                className="btn danger small"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const res = await api.unlock();
                    toast(
                      res.removed.length
                        ? `Removed lock file(s): ${res.removed.join(", ")}`
                        : "No lock files found",
                      "success",
                    );
                    await load();
                  } catch (e) {
                    toast(String((e as Error).message), "error");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Remove lock &amp; retry
              </button>
            )}
          </div>
          <div className="mono">{status.last_error}</div>
        </div>
      )}

      {busy && <BackupProgress logs={backupLogs} />}

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <div className="card">
          <h3>Last backup</h3>
          <div className="stat">{timeAgo(status.last_commit?.date)}</div>
          <div className="stat-sub">{formatDate(status.last_commit?.date)}</div>
        </div>
        <div className="card">
          <h3>Pending changes</h3>
          <div className={`stat ${status.pending_changes ? "amber" : "green"}`}>
            {status.pending_changes}
          </div>
          <div className="stat-sub">
            {status.clean ? "Working tree clean" : "Uncommitted changes"}
          </div>
        </div>
        <div className="card">
          <h3>Sync state</h3>
          <div className="stat">
            {status.ahead > 0 ? (
              <span className="amber">{status.ahead} ahead</span>
            ) : (
              <span className="green">up to date</span>
            )}
          </div>
          <div className="stat-sub">
            {status.behind > 0 ? `${status.behind} behind remote` : "in sync with remote"}
          </div>
        </div>
      </div>

      <div className="grid cols-3" style={{ marginBottom: 24 }}>
        <div className="card">
          <h3>Repository size</h3>
          <div className="stat">{formatBytes(status.repo_size_bytes)}</div>
          <div className="stat-sub">git history on disk</div>
        </div>
        <div className="card">
          <h3>Last commit</h3>
          <div className="mono" style={{ fontSize: 14 }}>
            {status.last_commit?.short_sha ?? "—"}
          </div>
          <div className="stat-sub">{status.last_commit?.subject ?? "no commits yet"}</div>
        </div>
        <div className="card">
          <h3>Docker</h3>
          <div className={`stat ${status.docker_available ? "green" : "muted"}`}>
            {status.docker_available ? "connected" : "unavailable"}
          </div>
          <div className="stat-sub">used for restore stop/start</div>
        </div>
      </div>

      <div className="row">
        <button className="btn" onClick={doBackup} disabled={busy}>
          Back up now
        </button>
        <button className="btn secondary" onClick={doPush} disabled={busy}>
          Push now
        </button>
      </div>
    </>
  );
}
