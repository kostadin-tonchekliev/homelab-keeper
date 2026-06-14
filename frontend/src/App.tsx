import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import { Dashboard } from "./pages/Dashboard";
import { History } from "./pages/History";
import { Logs } from "./pages/Logs";
import { Services } from "./pages/Services";
import { SettingsPage } from "./pages/Settings";

const nav = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/services", label: "Services" },
  { to: "/history", label: "History" },
  { to: "/settings", label: "Settings" },
  { to: "/logs", label: "Logs" },
];

export default function App() {
  return (
    <ToastProvider>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <span className="dot" />
            Homelab Backup
          </div>
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </aside>
        <main className="main">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/services" element={<Services />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/logs" element={<Logs />} />
          </Routes>
        </main>
      </div>
    </ToastProvider>
  );
}
