import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Switch } from "../components/Switch";
import { useToast } from "../components/Toast";
import { formatBytes } from "../lib/format";
import type { BrowseItem, Service } from "../types";

// ---- Recursive browse tree -------------------------------------------------

function ChevronRight() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function ChevronDown() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

interface TreeProps {
  parentPath: string;
  depth: number;
  expandedPaths: Set<string>;
  browseCache: Map<string, BrowseItem[]>;
  browseLoading: Set<string>;
  onToggleExpand: (path: string) => void;
  onToggleExclude: (path: string, excluded: boolean) => void;
}

function BrowseRows({
  parentPath,
  depth,
  expandedPaths,
  browseCache,
  browseLoading,
  onToggleExpand,
  onToggleExclude,
}: TreeProps) {
  const items = browseCache.get(parentPath);
  if (!items) return null;

  return (
    <>
      {items.map((item) => {
        const isExpanded = expandedPaths.has(item.rel_path);
        const isLoading = browseLoading.has(item.rel_path);
        const indent = 20 * depth;

        return (
          <Fragment key={item.rel_path}>
            <tr
              style={{ opacity: item.excluded ? 0.45 : 1 }}
            >
              <td>
                <div className="row" style={{ gap: 6, paddingLeft: indent }}>
                  {item.is_dir ? (
                    <button
                      className="btn secondary small"
                      style={{ padding: "2px 4px", minWidth: 0 }}
                      onClick={() => onToggleExpand(item.rel_path)}
                      title={isExpanded ? "Collapse" : "Explore contents"}
                    >
                      {isLoading ? "…" : isExpanded ? <ChevronDown /> : <ChevronRight />}
                    </button>
                  ) : (
                    <span style={{ display: "inline-block", width: 24 }} />
                  )}
                  <span className="mono" style={{ fontSize: 13 }}>
                    {item.name}{item.is_dir ? "/" : ""}
                  </span>
                </div>
              </td>
              <td>
                <span style={{ marginRight: item.size_bytes > 100 * 1024 * 1024 ? 6 : 0 }}>
                  {item.size_bytes === -1 ? (
                    <span className="muted">…</span>
                  ) : (
                    formatBytes(item.size_bytes)
                  )}
                </span>
                {item.size_bytes > 100 * 1024 * 1024 && (
                  <span
                    className="badge amber"
                    title="May contain files exceeding GitHub's 100 MB limit"
                  >
                    &gt;100 MB
                  </span>
                )}
              </td>
              <td>
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <Switch
                    checked={!item.excluded}
                    onChange={(v) => onToggleExclude(item.rel_path, !v)}
                  />
                </div>
              </td>
            </tr>
            {item.is_dir && isExpanded && (
              <BrowseRows
                parentPath={item.rel_path}
                depth={depth + 1}
                expandedPaths={expandedPaths}
                browseCache={browseCache}
                browseLoading={browseLoading}
                onToggleExpand={onToggleExpand}
                onToggleExclude={onToggleExclude}
              />
            )}
          </Fragment>
        );
      })}
    </>
  );
}

// ---- Services page ---------------------------------------------------------

export function Services() {
  const [services, setServices] = useState<Service[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [browseCache, setBrowseCache] = useState<Map<string, BrowseItem[]>>(new Map());
  const [browseLoading, setBrowseLoading] = useState<Set<string>>(new Set());
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      setServices(await api.services());
      setLoadError(null);
    } catch (e) {
      const msg = String((e as Error).message);
      setServices((prev) => {
        if (prev === null) {
          setLoadError(msg);
        } else {
          toast(msg, "error");
        }
        return prev;
      });
    }
  }, [toast]);

  useEffect(() => {
    load();
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

  const handleToggleExclude = async (path: string, excluded: boolean) => {
    try {
      await api.toggleExclude(path, excluded);
      await load();
      // Refresh browse cache for all currently expanded paths so toggles
      // reflect the new excluded state without collapsing the tree.
      const refreshed = new Map<string, BrowseItem[]>();
      await Promise.all(
        Array.from(expandedPaths).map(async (ep) => {
          try {
            const { items } = await api.browse(ep);
            refreshed.set(ep, items);
          } catch { /* ignore */ }
        }),
      );
      setBrowseCache(refreshed);
    } catch (e) {
      toast(String((e as Error).message), "error");
    }
  };

  const toggleExpand = async (path: string) => {
    if (expandedPaths.has(path)) {
      setExpandedPaths((prev) => {
        const next = new Set(prev);
        next.delete(path);
        return next;
      });
      return;
    }
    // Fetch contents if not yet cached.
    if (!browseCache.has(path)) {
      setBrowseLoading((prev) => new Set(prev).add(path));
      try {
        const { items } = await api.browse(path);
        setBrowseCache((prev) => new Map(prev).set(path, items));
      } catch (e) {
        toast(String((e as Error).message), "error");
        setBrowseLoading((prev) => {
          const next = new Set(prev);
          next.delete(path);
          return next;
        });
        return;
      }
      setBrowseLoading((prev) => {
        const next = new Set(prev);
        next.delete(path);
        return next;
      });
    }
    setExpandedPaths((prev) => new Set(prev).add(path));
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
        Toggle whole services or individual directories and files. Excluded
        paths are skipped in every backup and not watched for changes. Click{" "}
        <ChevronRight /> on any directory to explore its contents.
      </p>
      <p className="page-sub" style={{ marginTop: 4 }}>
        <span className="amber" style={{ fontWeight: 500 }}>Note:</span>{" "}
        GitHub enforces a 100&nbsp;MB per-file limit. Any single file above that
        threshold is automatically excluded from each commit — exclude the
        containing directory here to keep things tidy.
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
                    <th style={{ width: 150 }}>Size</th>
                    <th style={{ width: 130, textAlign: "right" }}>Back up</th>
                  </tr>
                </thead>
                <tbody>
                  {svc.subdirs.map((sub) => {
                    const isExpanded = expandedPaths.has(sub.rel_path);
                    const isLoading = browseLoading.has(sub.rel_path);
                    return (
                      <Fragment key={sub.rel_path}>
                        <tr
                          style={{ opacity: sub.excluded ? 0.45 : 1 }}
                        >
                          <td>
                            <div className="row" style={{ gap: 6 }}>
                              <button
                                className="btn secondary small"
                                style={{ padding: "2px 4px", minWidth: 0 }}
                                onClick={() => toggleExpand(sub.rel_path)}
                                title={isExpanded ? "Collapse" : "Explore contents"}
                              >
                                {isLoading ? "…" : isExpanded ? <ChevronDown /> : <ChevronRight />}
                              </button>
                              <span className="mono">{sub.name}</span>
                            </div>
                          </td>
                          <td>
                            <span style={{ marginRight: sub.size_bytes > 100 * 1024 * 1024 ? 6 : 0 }}>
                              {sub.size_bytes === -1 ? (
                                <span className="muted">calculating…</span>
                              ) : (
                                formatBytes(sub.size_bytes)
                              )}
                            </span>
                            {sub.size_bytes > 100 * 1024 * 1024 && (
                              <span
                                className="badge amber"
                                title="May contain files exceeding GitHub's 100 MB limit"
                              >
                                &gt;100 MB
                              </span>
                            )}
                          </td>
                          <td>
                            <div className="row" style={{ justifyContent: "flex-end" }}>
                              <Switch
                                checked={!sub.excluded}
                                onChange={(v) => handleToggleExclude(sub.rel_path, !v)}
                              />
                            </div>
                          </td>
                        </tr>
                        {isExpanded && (
                          <BrowseRows
                            parentPath={sub.rel_path}
                            depth={1}
                            expandedPaths={expandedPaths}
                            browseCache={browseCache}
                            browseLoading={browseLoading}
                            onToggleExpand={toggleExpand}
                            onToggleExclude={handleToggleExclude}
                          />
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
