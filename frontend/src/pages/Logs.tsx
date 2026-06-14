import { useEffect, useState } from "react";
import { api } from "../api";
import { formatDate } from "../lib/format";
import type { LogEntry } from "../types";

const colors: Record<string, string> = {
  info: "muted",
  success: "green",
  warning: "amber",
  error: "red",
};

export function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const load = async () => {
    try {
      setLogs(await api.logs(300));
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    load();
    const id = window.setInterval(load, 4000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <>
      <h1 className="page-title">Logs</h1>
      <p className="page-sub">Recent backup, push and restore activity.</p>
      <div className="card" style={{ padding: 0 }}>
        {logs.length === 0 ? (
          <div className="empty">No activity yet.</div>
        ) : (
          logs.map((l, i) => (
            <div className="log-line" key={i}>
              <span className="ts">{formatDate(l.ts)}</span>
              <span className={`lvl ${colors[l.level]}`}>{l.level}</span>
              <span>{l.message}</span>
            </div>
          ))
        )}
      </div>
    </>
  );
}
