"use client";

/**
 * Auth state lives here: who's logged in, their tokens, and the
 * login/logout/register actions. Tokens are kept in localStorage —
 * this is a real deployed app (not a Claude.ai artifact), so
 * localStorage is the normal, correct choice here, not the
 * in-memory-only restriction that applies to artifacts.
 */
import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authApi, UserOut } from "./api";

const ACCESS_TOKEN_KEY = "dermai_access_token";
const REFRESH_TOKEN_KEY = "dermai_refresh_token";

interface AuthContextValue {
  user: UserOut | null;
  accessToken: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ mfaRequired: boolean; mfaPendingToken?: string }>;
  completeMfaLogin: (mfaPendingToken: string, code: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; hospital_slug?: string | null }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const loadUser = useCallback(async (token: string) => {
    try {
      const me = await authApi.me(token);
      setUser(me);
      return me;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (stored) {
      setAccessToken(stored);
      loadUser(stored).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [loadUser]);

  function persistTokens(access: string, refresh: string) {
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
    setAccessToken(access);
  }

  async function login(email: string, password: string) {
    const res = await authApi.login({ email, password });
    if (res.mfa_required) {
      return { mfaRequired: true, mfaPendingToken: res.mfa_pending_token };
    }
    persistTokens(res.access_token!, res.refresh_token!);
    await loadUser(res.access_token!);
    return { mfaRequired: false };
  }

  async function completeMfaLogin(mfaPendingToken: string, code: string) {
    const tokens = await authApi.mfaLoginVerify({ mfa_pending_token: mfaPendingToken, code });
    persistTokens(tokens.access_token, tokens.refresh_token);
    await loadUser(tokens.access_token);
  }

  async function register(data: { email: string; password: string; full_name: string; hospital_slug?: string | null }) {
    await authApi.register(data);
    await login(data.email, data.password);
  }

  async function logout() {
    const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (refresh) {
      try {
        await authApi.logout(refresh);
      } catch {
        // best-effort — clear local state regardless
      }
    }
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setAccessToken(null);
    setUser(null);
    router.push("/login");
  }

  async function refreshUser() {
    if (accessToken) await loadUser(accessToken);
  }

  return (
    <AuthContext.Provider value={{ user, accessToken, loading, login, completeMfaLogin, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
