import { createContext, useContext, useEffect, useState } from "react";
import { loginApi, setAuthToken } from "../services/api";

const AuthContext = createContext(null);
const STORAGE_KEY = "valli_auth_user";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  // Restores the axios Authorization header on reload -- setUser() alone
  // only persists `user`, not the token api.js's interceptor reads.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const stored = raw ? JSON.parse(raw) : null;
      if (stored?.accessToken) setAuthToken(stored.accessToken);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    else localStorage.removeItem(STORAGE_KEY);
  }, [user]);

  async function login(email, password) {
    if (!email.trim() || !password.trim()) {
      return { ok: false, error: "Enter both an email and a password." };
    }
    try {
      const data = await loginApi(email.trim(), password);
      setAuthToken(data.access_token);
      setUser({
        email: data.user.email,
        role: data.user.role,
        id: data.user.id,
        accessToken: data.access_token,
        loggedInAt: new Date().toISOString(),
      });
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err.message || "Login failed." };
    }
  }

  function logout() {
    setAuthToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
