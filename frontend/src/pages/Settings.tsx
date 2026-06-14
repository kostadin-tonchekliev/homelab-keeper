import { useEffect, useState } from "react";
import { api } from "../api";
import { Switch } from "../components/Switch";
import { useToast } from "../components/Toast";
import type { Settings, SyncMode } from "../types";

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = async () => {
    try {
      setSettings(await api.settings());
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const update = (patch: Partial<Settings>) =>
    setSettings((s) => (s ? { ...s, ...patch } : s));

  const save = async () => {
    if (!settings) return;
    setBusy(true);
    try {
      const body: Partial<Settings> & { github_token?: string } = {
        services_dir: settings.services_dir,
        repo_url: settings.repo_url,
        branch: settings.branch,
        git_author_name: settings.git_author_name,
        git_author_email: settings.git_author_email,
        sync_mode: settings.sync_mode,
        interval_seconds: settings.interval_seconds,
        debounce_seconds: settings.debounce_seconds,
        auto_push: settings.auto_push,
        stop_containers_on_restore: settings.stop_containers_on_restore,
        notify_webhook_url: settings.notify_webhook_url,
        notify_on_success: settings.notify_on_success,
        notify_on_failure: settings.notify_on_failure,
      };
      if (token) body.github_token = token;
      const updated = await api.updateSettings(body);
      setSettings(updated);
      setToken("");
      toast("Settings saved", "success");
    } catch (e) {
      toast(String((e as Error).message), "error");
    } finally {
      setBusy(false);
    }
  };

  const connect = async () => {
    setBusy(true);
    try {
      await save();
      await api.init();
      toast("Repository connected and initialised", "success");
      await load();
    } catch (e) {
      toast(String((e as Error).message), "error");
    } finally {
      setBusy(false);
    }
  };

  if (!settings) return <div className="empty">Loading…</div>;

  return (
    <>
      <h1 className="page-title">Settings</h1>
      <p className="page-sub">
        {settings.initialized ? (
          <span className="green">Repository connected</span>
        ) : (
          <span className="amber">Not connected yet</span>
        )}
      </p>

      <div className="grid cols-2">
        <div className="card">
          <h3>Repository</h3>
          <div className="field">
            <label>Services directory</label>
            <input
              value={settings.services_dir}
              onChange={(e) => update({ services_dir: e.target.value })}
            />
            <div className="hint">Path inside the container (mounted from your host).</div>
          </div>
          <div className="field">
            <label>GitHub repository URL (private)</label>
            <input
              value={settings.repo_url}
              placeholder="https://github.com/you/homelab-backup.git"
              onChange={(e) => update({ repo_url: e.target.value })}
              style={
                settings.repo_url.startsWith("git@") || settings.repo_url.startsWith("ssh://")
                  ? { borderColor: "var(--red)" }
                  : {}
              }
            />
            {settings.repo_url.startsWith("git@") || settings.repo_url.startsWith("ssh://") ? (
              <div className="hint red">
                SSH URLs are not supported. Use the HTTPS URL instead:{" "}
                <span className="mono">https://github.com/&lt;user&gt;/&lt;repo&gt;.git</span>
              </div>
            ) : (
              <div className="hint">Must be HTTPS — SSH URLs are not supported.</div>
            )}
          </div>
          <div className="field">
            <label>Branch</label>
            <input
              value={settings.branch}
              onChange={(e) => update({ branch: e.target.value })}
            />
          </div>
          <div className="field">
            <label>GitHub token (PAT)</label>
            <input
              type="password"
              value={token}
              placeholder={settings.has_token ? "•••••••• (stored)" : "ghp_…"}
              onChange={(e) => setToken(e.target.value)}
            />
            <div className="hint">
              Fine-grained, repo-scoped. Stored locally, never committed.
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Sync behaviour</h3>
          <div className="field">
            <label>Sync mode</label>
            <select
              value={settings.sync_mode}
              onChange={(e) => update({ sync_mode: e.target.value as SyncMode })}
            >
              <option value="hybrid">Hybrid (watch + interval)</option>
              <option value="watch">On change only</option>
              <option value="interval">Interval only</option>
            </select>
          </div>
          <div className="field">
            <label>Interval (seconds)</label>
            <input
              type="number"
              value={settings.interval_seconds}
              onChange={(e) =>
                update({ interval_seconds: Number(e.target.value) })
              }
            />
          </div>
          <div className="field">
            <label>Debounce (seconds)</label>
            <input
              type="number"
              value={settings.debounce_seconds}
              onChange={(e) =>
                update({ debounce_seconds: Number(e.target.value) })
              }
            />
            <div className="hint">Quiet period after a change before backing up.</div>
          </div>
          <div className="row between field">
            <label style={{ margin: 0 }}>Auto-push after commit</label>
            <Switch
              checked={settings.auto_push}
              onChange={(v) => update({ auto_push: v })}
            />
          </div>
          <div className="row between field">
            <label style={{ margin: 0 }}>Stop containers during restore</label>
            <Switch
              checked={settings.stop_containers_on_restore}
              onChange={(v) => update({ stop_containers_on_restore: v })}
            />
          </div>
        </div>

        <div className="card">
          <h3>Git identity</h3>
          <div className="field">
            <label>Author name</label>
            <input
              value={settings.git_author_name}
              onChange={(e) => update({ git_author_name: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Author email</label>
            <input
              value={settings.git_author_email}
              onChange={(e) => update({ git_author_email: e.target.value })}
            />
          </div>
        </div>

        <div className="card">
          <h3>Notifications</h3>
          <div className="field">
            <label>Webhook URL (ntfy / Discord / Gotify)</label>
            <input
              value={settings.notify_webhook_url ?? ""}
              placeholder="https://ntfy.sh/my-topic"
              onChange={(e) => update({ notify_webhook_url: e.target.value })}
            />
          </div>
          <div className="row between field">
            <label style={{ margin: 0 }}>Notify on success</label>
            <Switch
              checked={settings.notify_on_success}
              onChange={(v) => update({ notify_on_success: v })}
            />
          </div>
          <div className="row between field">
            <label style={{ margin: 0 }}>Notify on failure</label>
            <Switch
              checked={settings.notify_on_failure}
              onChange={(v) => update({ notify_on_failure: v })}
            />
          </div>
        </div>
      </div>

      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn secondary" onClick={save} disabled={busy}>
          Save settings
        </button>
        <button className="btn" onClick={connect} disabled={busy}>
          {settings.initialized ? "Reconnect repository" : "Connect & initialise"}
        </button>
      </div>
    </>
  );
}
