import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export type LoginResult =
  | { kind: "ok"; user: User; warning?: string }
  | { kind: "mfa"; tempToken: string };

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<LoginResult>;
  loginMfa: (tempToken: string, code: string, remember: boolean) => Promise<LoginResult>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  /** True after the user logged out themselves (vs. a session that expired). */
  signedOutOnPurpose: boolean;
}

const AuthContext = React.createContext<AuthState | null>(null);

async function fetchMe(): Promise<User | null> {
  try {
    const { data } = await api.get<User>("/auth/me");
    return data;
  } catch {
    // 401 after a failed refresh = signed out. Anything else also means we
    // cannot vouch for a session, so treat it the same way.
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: 5 * 60_000, retry: false });
  const [signedOutOnPurpose, setSignedOutOnPurpose] = React.useState(false);

  const login = React.useCallback(
    async (email: string, password: string, remember: boolean): Promise<LoginResult> => {
      const { data } = await api.post("/auth/login", { email, password, remember_me: remember });
      if (data.mfa_required) return { kind: "mfa", tempToken: data.temp_token };
      setSignedOutOnPurpose(false);
      qc.setQueryData(["me"], data.user);
      return { kind: "ok", user: data.user };
    },
    [qc],
  );

  const loginMfa = React.useCallback(
    async (tempToken: string, code: string, remember: boolean): Promise<LoginResult> => {
      const { data } = await api.post("/auth/login/mfa", { temp_token: tempToken, totp_code: code, remember_me: remember });
      setSignedOutOnPurpose(false);
      qc.setQueryData(["me"], data.user);
      return { kind: "ok", user: data.user, warning: data.warning };
    },
    [qc],
  );

  const logout = React.useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setSignedOutOnPurpose(true);
      // Order matters. Set "me" to null FIRST so the live observer in this
      // provider is notified and every screen sees the user as signed out.
      // qc.clear() would remove the "me" query out from under that observer,
      // which then keeps showing the old user ("Open dashboard" after logout).
      qc.setQueryData(["me"], null);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    }
  }, [qc]);

  const refreshUser = React.useCallback(async () => {
    await qc.invalidateQueries({ queryKey: ["me"] });
  }, [qc]);

  const value = React.useMemo<AuthState>(
    () => ({
      user: me.data ?? null,
      loading: me.isPending,
      login,
      loginMfa,
      logout,
      refreshUser,
      signedOutOnPurpose,
    }),
    [me.data, me.isPending, login, loginMfa, logout, refreshUser, signedOutOnPurpose],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
