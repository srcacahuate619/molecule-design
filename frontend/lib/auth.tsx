"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type User = {
  user_id: string;
  username: string;
  email: string;
};

type AuthContextType = {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: string, id_token: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

import { API_URL } from "./config";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem("moldesign_auth");
    if (stored) {
      try {
        const data = JSON.parse(stored);
        setToken(data.token);
        setRefreshToken(data.refreshToken);
        setUser(data.user);
      } catch {
        localStorage.removeItem("moldesign_auth");
      }
    }
    setIsLoading(false);

    // Escuchar el evento de expiración desde api.ts
    const handleAuthExpired = () => {
      setToken(null);
      setRefreshToken(null);
      setUser(null);
      localStorage.removeItem("moldesign_auth");
    };
    window.addEventListener('auth_expired', handleAuthExpired);
    return () => window.removeEventListener('auth_expired', handleAuthExpired);
  }, []);

  const _persist = useCallback((tok: string, refTok: string, u: User) => {
    setToken(tok);
    setRefreshToken(refTok);
    setUser(u);
    localStorage.setItem(
      "moldesign_auth",
      JSON.stringify({ token: tok, refreshToken: refTok, user: u })
    );
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      _persist(data.access_token, data.refresh_token, {
        user_id: data.user_id,
        username: data.username,
        email: data.email,
      });
    },
    [_persist]
  );

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, username, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      _persist(data.access_token, data.refresh_token, {
        user_id: data.user_id,
        username: data.username,
        email: data.email,
      });
    },
    [_persist]
  );

  const loginWithOAuth = useCallback(
    async (provider: string, id_token: string) => {
      const res = await fetch(`${API_URL}/auth/oauth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, id_token }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
            throw new Error("Debe registrarse primero para usar esta cuenta.");
        }
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      _persist(data.access_token, data.refresh_token, {
        user_id: data.user_id,
        username: data.username,
        email: data.email,
      });
    },
    [_persist]
  );

  const logout = useCallback(() => {
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    localStorage.removeItem("moldesign_auth");
  }, []);

  const value = useMemo(
    () => ({ user, token, refreshToken, isLoading, login, register, loginWithOAuth, logout }),
    [user, token, refreshToken, isLoading, login, register, loginWithOAuth, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
