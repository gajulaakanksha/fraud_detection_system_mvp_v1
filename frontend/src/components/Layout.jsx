import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Icon from "./Icon";
import ThemeToggle from "./ThemeToggle";
import "./Layout.css";

const NAV_ITEMS = [
  { to: "/app/overview", label: "Overview", icon: "grid" },
  { to: "/app/analyser", label: "Transaction Analyser", icon: "activity" },
  { to: "/app/report", label: "Report", icon: "file" },
];

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark">
            <Icon name="shield" size={16} color="#ffffff" />
          </div>
          <span>Valli SecurePay AI</span>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
            >
              <Icon name={item.icon} size={17} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-avatar">{(user?.name ?? "?").charAt(0)}</div>
            <div className="sidebar-user-meta">
              <div className="sidebar-user-name">{user?.name}</div>
              <div className="sidebar-user-email">{user?.email}</div>
            </div>
          </div>
          <ThemeToggle />
          <button className="sidebar-logout" onClick={logout} title="Sign out">
            <Icon name="logout" size={16} />
          </button>
        </div>
      </aside>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
