import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Icon from "../components/Icon";
import "./AuthPages.css";

const PASSWORD_RULES = [
  { label: "8+ characters", test: (password) => password.length >= 8 && password.length <= 64 },
  { label: "Upper & lowercase", test: (password) => /[a-z]/.test(password) && /[A-Z]/.test(password) },
  { label: "At least 1 digit", test: (password) => /\d/.test(password) },
  { label: "At least 1 symbol", test: (password) => /[^\w\s]/.test(password) },
];
const USERNAME_PATTERN = /^[a-zA-Z0-9_.]{3,30}$/;
const RESEND_AFTER_SECONDS = 60;

function AuthLayout({ title, subtitle, children }) {
  return (
    <main className="page">
      <div className="auth-layout">
        <section className="card auth-card stack-large">
          <div>
            <h1 className="auth-title">{title}</h1>
            <p className="muted" style={{ marginTop: 8 }}>{subtitle}</p>
          </div>
          {children}
        </section>
        <aside className="auth-aside stack-large">
          <span className="eyebrow">Why an account?</span>
          <h2>Checking fruit needs no account</h2>
          <p className="small muted">An account lets you improve the model:</p>
          {[
            ["upload", "Add labelled photos", "Upload fruit photos of any of the 16 classes, several classes at once."],
            ["refresh", "Retrain the model", "Fine-tune the current model on the original data plus your photos, and follow it live."],
            ["layers", "Compare & choose", "Compare the new model with the previous one on the same test images, and pick the one that answers."],
          ].map(([icon, title, text]) => (
            <div key={title} className="row" style={{ alignItems: "flex-start", gap: 12 }}>
              <span className="guideline-icon"><Icon name={icon} /></span>
              <div><strong className="small">{title}</strong><p className="tiny muted">{text}</p></div>
            </div>
          ))}
        </aside>
      </div>
    </main>
  );
}

function PasswordChecklist({ password }) {
  return (
    <div className="checklist">
      {PASSWORD_RULES.map((rule) => {
        const passed = rule.test(password);
        return <span key={rule.label} className={passed ? "passed" : ""}><Icon name={passed ? "check" : "close"} size={13} />{rule.label}</span>;
      })}
    </div>
  );
}

const passwordIsStrong = (password) => PASSWORD_RULES.every((rule) => rule.test(password));

// password field with a button to show or hide what was typed
function PasswordInput({ className = "input", ...inputProps }) {
  const [visible, setVisible] = useState(false);
  return (
    <span className="password-field">
      <input {...inputProps} className={className} type={visible ? "text" : "password"} />
      <button type="button" className="password-toggle" onClick={() => setVisible((shown) => !shown)}
        aria-label={visible ? "Hide password" : "Show password"} aria-pressed={visible}>
        <Icon name={visible ? "eyeOff" : "eye"} size={18} />
      </button>
    </span>
  );
}

// ------------------------------------------------------------ log in
export function LoginPage() {
  const { login, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate(location.state?.from && location.state.from !== "/login" ? location.state.from : "/retrain", { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Log in" subtitle="Log in to add training images, retrain the model and choose model versions.">
      {sessionExpired && <div className="alert warning"><Icon name="clock" />Your session expired. Please log in again.</div>}
      <form className="stack-large" onSubmit={submit}>
        <label className="field">Email or username
          <input className="input" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>
        <label className="field">
          <span className="field-row">Password <Link className="small" to="/password">Forgot password?</Link></span>
          <PasswordInput className="input" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {error && <div className="alert error"><Icon name="alert" />{error}</div>}
        <button className="button primary full" disabled={submitting}>{submitting && <span className="spinner" />} Log in</button>
      </form>
      <p className="small muted" style={{ textAlign: "center" }}>No account yet? <Link to="/register">Create an account</Link></p>
    </AuthLayout>
  );
}

// ------------------------------------------------------------ register
export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ first_name: "", last_name: "", username: "", email_address: "", password: "", confirm_password: "" });
  const [serverUsernameCheck, setServerUsernameCheck] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  // format is checked here; availability is asked to the server once the user stops typing
  const typedUsername = form.username.trim();
  const usernameFormatValid = USERNAME_PATTERN.test(typedUsername);
  useEffect(() => {
    if (!USERNAME_PATTERN.test(typedUsername)) return undefined;
    const timer = setTimeout(() => {
      api.usernameAvailable(typedUsername).then(setServerUsernameCheck).catch(() => setServerUsernameCheck(null));
    }, 400);
    return () => clearTimeout(timer);
  }, [typedUsername]);
  const usernameCheck = !typedUsername ? null
    : !usernameFormatValid ? { available: false, message: "3-30 letters, digits, _ or ." }
    : serverUsernameCheck?.username === typedUsername.toLowerCase() ? serverUsernameCheck : null;

  const passwordsMatch = form.confirm_password.length > 0 && form.password === form.confirm_password;
  const canSubmit = passwordIsStrong(form.password) && passwordsMatch && usernameCheck?.available !== false;

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.register({ ...form, username: form.username.trim(), email_address: form.email_address.trim() });
      navigate("/login", { replace: true, state: { registered: true } });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="Join to contribute labelled photos and retrain the model.">
      <form className="stack-large" onSubmit={submit}>
        <div className="grid grid-2" style={{ gap: 14 }}>
          <label className="field">First name<input className="input" autoComplete="given-name" value={form.first_name} onChange={update("first_name")} required /></label>
          <label className="field">Last name<input className="input" autoComplete="family-name" value={form.last_name} onChange={update("last_name")} required /></label>
        </div>
        <label className="field">Username
          <input className={`input ${usernameCheck?.available === false ? "invalid" : ""}`} autoComplete="username" value={form.username} onChange={update("username")} required />
          <span className={`hint ${usernameCheck ? (usernameCheck.available ? "good" : "bad") : ""}`}>
            {usernameCheck ? usernameCheck.message : "3-30 letters, digits, _ or ."}
          </span>
        </label>
        <label className="field">Email<input className="input" type="email" autoComplete="email" value={form.email_address} onChange={update("email_address")} required /></label>
        <label className="field">Password
          <PasswordInput className="input" autoComplete="new-password" value={form.password} onChange={update("password")} required />
        </label>
        <PasswordChecklist password={form.password} />
        <label className="field">Confirm password
          <PasswordInput className={`input ${form.confirm_password && !passwordsMatch ? "invalid" : ""}`} autoComplete="new-password" value={form.confirm_password} onChange={update("confirm_password")} required />
          {form.confirm_password && <span className={`hint ${passwordsMatch ? "good" : "bad"}`}>{passwordsMatch ? "Passwords match" : "Passwords do not match"}</span>}
        </label>
        {error && <div className="alert error"><Icon name="alert" />{error}</div>}
        <button className="button primary full" disabled={!canSubmit || submitting}>{submitting && <span className="spinner" />} Create account</button>
      </form>
      <p className="small muted" style={{ textAlign: "center" }}>Already have an account? <Link to="/login">Log in</Link></p>
    </AuthLayout>
  );
}

// ------------------------------------------------------------ change or reset password
export function PasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState("email");
  const [emailAddress, setEmailAddress] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resendIn, setResendIn] = useState(0);
  const [message, setMessage] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (resendIn <= 0) return undefined;
    const timer = setTimeout(() => setResendIn((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  async function sendCode(event) {
    event?.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      const response = await api.requestPasswordCode(emailAddress.trim());
      setMessage({ type: "success", text: response.message });
      setStep("code");
      setResendIn(RESEND_AFTER_SECONDS);
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setSubmitting(false);
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      await api.changePassword({ email_address: emailAddress.trim(), code, new_password: newPassword, confirm_password: confirmPassword });
      setStep("done");
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setSubmitting(false);
    }
  }

  const passwordsMatch = confirmPassword.length > 0 && newPassword === confirmPassword;

  return (
    <AuthLayout title="Change your password" subtitle="Works for a forgotten password too: we email you a 6-digit code.">
      {step === "email" && (
        <form className="stack-large" onSubmit={sendCode}>
          <label className="field">Email<input className="input" type="email" autoComplete="email" value={emailAddress} onChange={(event) => setEmailAddress(event.target.value)} required /></label>
          {message && <div className={`alert ${message.type}`}>{message.text}</div>}
          <button className="button primary full" disabled={submitting}>{submitting && <span className="spinner" />}<Icon name="mail" /> Send code</button>
        </form>
      )}

      {step === "code" && (
        <form className="stack-large" onSubmit={changePassword}>
          <div className="alert success"><Icon name="mail" />If {emailAddress} is registered, a code is on its way. It expires in 10 minutes.</div>
          <label className="field">6-digit code
            <input className="input code-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} required />
          </label>
          <label className="field">New password
            <PasswordInput className="input" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
          </label>
          <PasswordChecklist password={newPassword} />
          <label className="field">Confirm new password
            <PasswordInput className={`input ${confirmPassword && !passwordsMatch ? "invalid" : ""}`} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
          </label>
          {message?.type === "error" && <div className="alert error"><Icon name="alert" />{message.text}</div>}
          <button className="button primary full" disabled={submitting || code.length !== 6 || !passwordIsStrong(newPassword) || !passwordsMatch}>
            {submitting && <span className="spinner" />} Change password
          </button>
          <button type="button" className="button ghost" disabled={resendIn > 0 || submitting} onClick={sendCode}>
            {resendIn > 0 ? `Resend code in ${resendIn}s` : "Resend code"}
          </button>
        </form>
      )}

      {step === "done" && (
        <div className="stack-large">
          <div className="alert success"><Icon name="checkCircle" />Password changed. You can now log in with your new password.</div>
          <button className="button primary full" onClick={() => navigate("/login")}>Go to log in</button>
        </div>
      )}

      <p className="small muted" style={{ textAlign: "center" }}><Link to="/login">← Back to log in</Link></p>
    </AuthLayout>
  );
}
