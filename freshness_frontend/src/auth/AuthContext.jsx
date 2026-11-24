import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, onSessionExpired, readToken, saveToken } from "../api/client";

const AuthContext = createContext(null);

// email inside the JWT (not verified here: the server checks the token on every request)
function emailFromToken(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    return payload.sub || null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    const savedToken = readToken();
    return savedToken && emailFromToken(savedToken) ? savedToken : null;
  });
  const [sessionExpired, setSessionExpired] = useState(false);

  const logout = useCallback(() => {
    saveToken(null);
    setToken(null);
  }, []);

  useEffect(() => onSessionExpired(() => {
    setSessionExpired(true);
    logout();
  }), [logout]);

  const login = useCallback(async (username, password) => {
    const { access_token: accessToken } = await api.login(username, password);
    saveToken(accessToken);
    setToken(accessToken);
    setSessionExpired(false);
  }, []);

  const value = useMemo(() => ({
    isLoggedIn: Boolean(token),
    emailAddress: token ? emailFromToken(token) : null,
    sessionExpired,
    login,
    logout,
  }), [token, sessionExpired, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
