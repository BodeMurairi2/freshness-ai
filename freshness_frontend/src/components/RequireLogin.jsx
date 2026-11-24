import { Link, useLocation } from "react-router";
import { useAuth } from "../auth/AuthContext";
import Icon from "./Icon";

// Retrain and Models need an account: visitors see why, with a way in
export default function RequireLogin({ title, children }) {
  const { isLoggedIn, sessionExpired } = useAuth();
  const location = useLocation();
  if (isLoggedIn) return children;

  return (
    <main className="page">
      <div className="card stack-large" style={{ maxWidth: 560, margin: "40px auto", textAlign: "center", alignItems: "center" }}>
        <span className="brand-logo" style={{ width: 52, height: 52, borderRadius: 16 }}><Icon name="lock" size={24} /></span>
        <h2>{sessionExpired ? "Your session expired" : `Log in to ${title}`}</h2>
        <p className="muted">
          {sessionExpired
            ? "Please log in again to continue."
            : "Checking fruit needs no account. An account lets you add training images, retrain the model and choose which model answers predictions."}
        </p>
        <div className="row-wrap" style={{ justifyContent: "center" }}>
          <Link className="button primary" to="/login" state={{ from: location.pathname }}>Log in</Link>
          <Link className="button secondary" to="/register">Create an account</Link>
        </div>
      </div>
    </main>
  );
}
