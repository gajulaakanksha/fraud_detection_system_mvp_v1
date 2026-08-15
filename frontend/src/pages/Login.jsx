import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Icon from "../components/Icon";
import "./Login.css";

const FEATURES = [
  { icon: "zap", label: "AI-Powered Risk Detection" },
  { icon: "shield", label: "Real-time Fraud Prevention" },
  { icon: "trendingUp", label: "Explainable AI Analytics" },
  { icon: "lock", label: "Enterprise-Grade Security" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const from = location.state?.from?.pathname ?? "/app/overview";

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    const result = await login(email, password);
    setSubmitting(false);
    if (result.ok) navigate(from, { replace: true });
    else setError(result.error);
  }

  return (
    <div className="login-screen">
      <aside className="login-brand-panel">
        <div className="login-brand-mark">
          <Icon name="shield" size={40} color="#ffffff" />
        </div>
        <h1 className="login-wordmark">Valli SecurePay AI</h1>
        <p className="login-tagline">Risk Intelligence Engine</p>

        <ul className="login-features">
          {FEATURES.map((f) => (
            <li key={f.label}>
              <span className="login-feature-icon">
                <Icon name={f.icon} size={16} color="#f97316" />
              </span>
              {f.label}
            </li>
          ))}
        </ul>
      </aside>

      <main className="login-form-panel">
        <div className="login-form-wrap">
          <h2>Welcome Back</h2>
          <p className="login-sub">Sign in to access the Risk Intelligence Platform</p>

          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>
                <Icon name="mail" size={13} color="#f97316" /> Email Address
              </span>
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@bank.com"
                required
              />
            </label>
            <label className="field">
              <span>
                <Icon name="lock" size={13} color="#f97316" /> Password
              </span>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </label>

            <div className="login-row">
              <label className="login-remember">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                Remember me
              </label>
              <a href="#" onClick={(e) => e.preventDefault()} className="login-forgot">
                Forgot password?
              </a>
            </div>

            {error && <div className="login-error">{error}</div>}

            <button type="submit" className="login-submit" disabled={submitting}>
              {submitting && <span className="spinner" />}
              {submitting ? "Signing in…" : "Sign In"}
              {!submitting && <Icon name="arrowRight" size={16} color="#ffffff" />}
            </button>
          </form>

          <p className="login-footer">
            Powered by Valli SecurePay AI Fintech Technologies
            <br />
            Version 2.0 <span className="login-footer-dot">|</span> Enterprise Edition
          </p>
        </div>
      </main>
    </div>
  );
}
