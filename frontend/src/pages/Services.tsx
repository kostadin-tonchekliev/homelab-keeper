import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Switch } from "../components/Switch";
import { useToast } from "../components/Toast";
import { formatBytes } from "../lib/format";
import type { Service } from "../types";

export function Services() {
  const [services, setServices] = useState<Service[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      setServices(await api.services());
      setLoadError(null);
    } catch (e) {
      const msg = String((e as Error).message);
      setServices((prev) => {
        if (prev === null) {
          // First load failure — show an error rather than freezing on "Loading…".
          setLoadError(msg);
        } else {
          // Already have data — keep it visible and only show a toast.
          toast(msg, "error");
        }
        return prev;
      });
    }
  }, [toast]);

  useEffect(() => {
    load();
    // Re-poll periodically so sizes fill in after background calculation finishes.
    const id = window.setInterval(load, 8000);
    return () => window.clearInterval(id);
  }, [load]);

  const toggleService = async (name: string, enabled: boolean) => {
    try {
      await api.toggleService(name, enabled);
      await load();
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  const toggleExclude = async (path: string, excluded: boolean) => {
    try {
      await api.toggleExclude(path, excluded);
      await load();
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  if (!services) {
    return (
      <div className="empty">
        {loadError ? (
          <>
            <div className="red" style={{ marginBottom: 8 }}>Failed to load services</div>
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

  return (
    <>
      <h1 className="page-title">Services</h1>
      <p className="page-sub">
        Toggle whole services or individual data directories. Excluded paths are
        skipped in every backup and not watched for changes.
      </p>

      {services.length === 0 && (
        <div className="card">
          <div className="empty">
            No services found. Check the services directory in Settings — each
            service must be a folder containing a compose file.
          </div>
        </div>
      )}

      <div className="grid" style={{ gap: 16 }}>
        {services.map((svc) => (
          <div className="card" key={svc.name}>
            <div className="row between">
              <div>
                <div className="row" style={{ gap: 10 }}>
                  <strong style={{ fontSize: 16 }}>{svc.name}</strong>
                  <span className="badge">{formatBytes(svc.size_bytes)}</span>
                  {svc.compose_file && (
                    <span className="mono muted">{svc.compose_file}</span>
                  )}
                </div>
              </div>
              <div className="row" style={{ gap: 10 }}>
                <span className="muted">{svc.enabled ? "Backed up" : "Skipped"}</span>
                <Switch
                  checked={svc.enabled}
                  onChange={(v) => toggleService(svc.name, v)}
                />
              </div>
            </div>

            {svc.enabled && svc.subdirs.length > 0 && (
              <table style={{ marginTop: 14 }}>
                <thead>
                  <tr>
                    <th>Directory</th>
                    <th style={{ width: 120 }}>Size</th>
                    <th style={{ width: 130, textAlign: "right" }}>Exclude</th>
                  </tr>
                </thead>
                <tbody>
                  {svc.subdirs.map((sub) => (
                    <tr key={sub.rel_path}>
                      <td className="mono">{sub.name}</td>
                      <td>{formatBytes(sub.size_bytes)}</td>
                      <td>
                        <div className="row" style={{ justifyContent: "flex-end" }}>
                          <Switch
                            checked={sub.excluded}
                            onChange={(v) => toggleExclude(sub.rel_path, v)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
