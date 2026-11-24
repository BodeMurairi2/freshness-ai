import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { FRUITS } from "../data/classes";
import Icon from "./Icon";
import "./Layout.css";

const CURRENT_YEAR = new Date().getFullYear();

const NAVIGATION = [
  { path: "/", label: "Predict", locked: false },
  { path: "/models", label: "Models", locked: false },
  { path: "/insights", label: "Insights", locked: false },
  { path: "/retrain", label: "Retrain", locked: true },
];

export default function Layout() {
  const { isLoggedIn, emailAddress, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand" aria-label="Freshness-ai home">
            <span className="brand-logo"><Icon name="leaf" size={18} /></span>
            <span>
              <span className="brand-name">Freshness-ai</span>
              <span className="brand-tagline">Fruit freshness classifier</span>
            </span>
          </Link>

          <nav className={`main-nav ${menuOpen ? "open" : ""}`} aria-label="Main">
            {NAVIGATION.map((item) => (
              <NavLink key={item.path} to={item.path} end={item.path === "/"} className="nav-link" onClick={() => setMenuOpen(false)}>
                {item.locked && !isLoggedIn && <Icon name="lock" size={13} />}
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="topbar-actions">
            {isLoggedIn ? (
              <div className="account">
                <span className="avatar" title={emailAddress}>{emailAddress?.charAt(0).toUpperCase()}</span>
                <button className="button ghost small" onClick={logout}>Log out</button>
              </div>
            ) : (
              <Link className="button secondary small" to="/login" state={{ from: location.pathname }}>Log in</Link>
            )}
            <button className="menu-button" onClick={() => setMenuOpen((open) => !open)}
              aria-label={menuOpen ? "Close menu" : "Open menu"} aria-expanded={menuOpen}>
              <Icon name={menuOpen ? "close" : "menu"} size={20} />
            </button>
          </div>
        </div>
      </header>

      <Outlet />

      <footer className="footer">
        <div className="footer-inner">
          <div className="row-wrap">
            <span className="eyebrow">Supported fruits:</span>
            {FRUITS.map((fruit) => <span key={fruit.key} className="pill">{fruit.name}</span>)}
          </div>
          <span className="tiny muted">© {CURRENT_YEAR} Freshness-ai</span>
        </div>
      </footer>
    </div>
  );
}
