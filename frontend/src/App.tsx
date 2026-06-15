import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ThemeToggle } from "./components/ThemeToggle";
import { ToastProvider } from "./components/Toast";
import { useTheme } from "./lib/theme";
import { Dashboard } from "./pages/Dashboard";
import { History } from "./pages/History";
import { Logs } from "./pages/Logs";
import { Services } from "./pages/Services";
import { SettingsPage } from "./pages/Settings";
import appVersionRaw from "../../VERSION?raw";

const APP_VERSION = appVersionRaw.trim();

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: GridIcon },
  { to: "/services", label: "Services", icon: StackIcon },
  { to: "/history", label: "History", icon: ClockIcon },
  { to: "/settings", label: "Settings", icon: GearIcon },
  { to: "/logs", label: "Logs", icon: TerminalIcon },
];

export default function App() {
  const { theme, toggle } = useTheme();

  return (
    <ToastProvider>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <span className="brand-mark">
              <ShieldIcon />
            </span>
            <div className="brand-text">
              <span className="brand-name">Homelab Keeper</span>
              <span className="brand-sub">Service keeper</span>
            </div>
          </div>

          <nav className="nav">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `nav-item ${isActive ? "active" : ""}`
                  }
                >
                  <span className="nav-icon">
                    <Icon />
                  </span>
                  {item.label}
                </NavLink>
              );
            })}
          </nav>

          <div className="sidebar-footer">
            <ThemeToggle theme={theme} onToggle={toggle} />
          </div>
        </aside>
        <main className="main">
          <div className="main-inner">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/services" element={<Services />} />
              <Route path="/history" element={<History />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/logs" element={<Logs />} />
            </Routes>
          </div>
          <footer className="app-footer">
            <a
              href="https://github.com/kostadin-tonchekliev/homelab-keeper"
              target="_blank"
              rel="noopener noreferrer"
              className="app-footer-link"
            >
              <GitHubIcon />
              homelab-keeper
            </a>
            <span className="app-footer-version">v{APP_VERSION}</span>
          </footer>
        </main>
      </div>
    </ToastProvider>
  );
}

function GitHubIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.009-.868-.013-1.703-2.782.605-3.369-1.34-3.369-1.34-.454-1.154-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.202 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function StackIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 2 9 5-9 5-9-5 9-5z" />
      <path d="m3 12 9 5 9-5" />
      <path d="m3 17 9 5 9-5" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function TerminalIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="m7 9 3 3-3 3M13 15h4" />
    </svg>
  );
}
