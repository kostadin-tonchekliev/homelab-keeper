import { useEffect, useState } from "react";
import { api } from "../api";
import { DiffView } from "../components/DiffView";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { formatDate } from "../lib/format";
import type { Commit, CommitFile } from "../types";

export function History() {
  const [commits, setCommits] = useState<Commit[] | null>(null);
  const [viewing, setViewing] = useState<Commit | null>(null);
  const [files, setFiles] = useState<CommitFile[]>([]);
  const [diff, setDiff] = useState<string>("");
  const [restoring, setRestoring] = useState<Commit | null>(null);
  const [restorePaths, setRestorePaths] = useState<string>("");
  const [restoreDiff, setRestoreDiff] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = async () => {
    try {
      setCommits(await api.history(100));
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openCommit = async (c: Commit) => {
    setViewing(c);
    setDiff("");
    try {
      const detail = await api.commitDetail(c.sha);
      setFiles(detail.files);
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  const showFileDiff = async (path: string) => {
    if (!viewing) return;
    try {
      const res = await api.diff(viewing.sha, path);
      setDiff(res.diff);
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  const openRestore = async (c: Commit) => {
    setRestoring(c);
    setRestorePaths("");
    setRestoreDiff("");
    try {
      const res = await api.restorePreview(c.sha, []);
      setRestoreDiff(res.diff);
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  const refreshPreview = async () => {
    if (!restoring) return;
    const paths = restorePaths
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    try {
      const res = await api.restorePreview(restoring.sha, paths);
      setRestoreDiff(res.diff);
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  const doRestore = async () => {
    if (!restoring) return;
    const paths = restorePaths
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    setBusy(true);
    try {
      const res = await api.restore(restoring.sha, paths);
      toast(
        `Restored from ${restoring.short_sha}` +
          (res.restarted?.length ? ` · restarted ${res.restarted.length} project(s)` : ""),
        "success",
      );
      setRestoring(null);
    } catch (e) {
      toast(String((e as Error).message), "error");
    } finally {
      setBusy(false);
    }
  };

  if (!commits) return <div className="empty">Loading…</div>;

  return (
    <>
      <h1 className="page-title">History</h1>
      <p className="page-sub">Every backup is a commit. View changes or restore any point.</p>

      {commits.length === 0 ? (
        <div className="card">
          <div className="empty">No backups yet.</div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 110 }}>Commit</th>
                <th>Message</th>
                <th style={{ width: 180 }}>When</th>
                <th style={{ width: 180, textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {commits.map((c) => (
                <tr key={c.sha}>
                  <td className="mono">{c.short_sha}</td>
                  <td>{c.subject}</td>
                  <td className="muted">{formatDate(c.date)}</td>
                  <td>
                    <div className="row" style={{ justifyContent: "flex-end" }}>
                      <button className="btn secondary small" onClick={() => openCommit(c)}>
                        View
                      </button>
                      <button className="btn small" onClick={() => openRestore(c)}>
                        Restore
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewing && (
        <Modal title={`Commit ${viewing.short_sha}`} onClose={() => setViewing(null)}>
          <p className="muted">{viewing.subject}</p>
          <div className="grid cols-2" style={{ gap: 16 }}>
            <div>
              <h3 style={{ fontSize: 13 }}>Files changed</h3>
              <table>
                <tbody>
                  {files.map((f) => (
                    <tr key={f.path} onClick={() => showFileDiff(f.path)} style={{ cursor: "pointer" }}>
                      <td className="mono">{f.path}</td>
                      <td className="green">+{f.added}</td>
                      <td className="red">-{f.removed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h3 style={{ fontSize: 13 }}>Diff</h3>
              {diff ? <DiffView diff={diff} /> : <div className="empty">Select a file</div>}
            </div>
          </div>
        </Modal>
      )}

      {restoring && (
        <Modal
          title={`Restore from ${restoring.short_sha}`}
          onClose={() => setRestoring(null)}
          footer={
            <>
              <button className="btn secondary" onClick={() => setRestoring(null)}>
                Cancel
              </button>
              <button className="btn danger" onClick={doRestore} disabled={busy}>
                Confirm restore
              </button>
            </>
          }
        >
          <div className="field">
            <label>Paths to restore (optional, comma-separated)</label>
            <input
              value={restorePaths}
              placeholder="e.g. audiobookshelf/config (leave empty for everything)"
              onChange={(e) => setRestorePaths(e.target.value)}
              onBlur={refreshPreview}
            />
            <div className="hint">
              Affected services' containers will be stopped during restore and
              started again afterwards (if enabled in Settings).
            </div>
          </div>
          <h3 style={{ fontSize: 13 }}>Preview (what will change in your live files)</h3>
          <DiffView diff={restoreDiff} />
        </Modal>
      )}
    </>
  );
}
