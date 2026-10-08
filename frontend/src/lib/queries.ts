import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type {
  AppConfig,
  Decision,
  DecisionStats,
  DecisionSummary,
  MarketRibbon,
  Portfolio,
  Profile,
  VerifyResult,
} from "./types";

export function useAppConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: async () => (await api.get<AppConfig>("/meta/config")).data,
    staleTime: Infinity,
  });
}

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get<{ profile: Profile }>("/users/me/profile")).data.profile,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: async () => (await api.get<DecisionStats>("/decisions/stats")).data,
  });
}

export function useDecisions(limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["decisions", limit, offset],
    queryFn: async () =>
      (
        await api.get<{ items: DecisionSummary[]; total: number }>("/decisions/my", {
          params: { limit, offset },
        })
      ).data,
  });
}

export function useDecision(id: string | undefined, opts: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: ["decision", id],
    enabled: Boolean(id),
    queryFn: async () => (await api.get<{ decision: Decision }>(`/decisions/${id}/result`)).data.decision,
    // Polling is the fallback when the live stream can't be opened.
    refetchInterval: (q) =>
      opts.poll && q.state.data && (q.state.data.status === "pending" || q.state.data.status === "processing")
        ? 2000
        : false,
  });
}

export interface MarketContext {
  nifty_1m_return: number | null;
  nifty_volatility_30d: number | null;
  nifty_1d_change: number | null;
  vix_value: number | null;
  market_trend: "bull" | "bear" | "sideways" | null;
  market_data_source: "live" | "cache" | "unavailable";
}

export function useMarketContext() {
  return useQuery({
    queryKey: ["market-context"],
    queryFn: async () => (await api.get<MarketContext>("/market/context")).data,
    staleTime: 5 * 60_000,
  });
}

export function useMarketRibbon() {
  return useQuery({
    queryKey: ["ribbon"],
    queryFn: async () => (await api.get<MarketRibbon>("/market/ribbon")).data,
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: async () => (await api.get<Portfolio>("/portfolio")).data,
    staleTime: 60_000,
  });
}

/** Run on demand (the "Verify this record" button), never in the background. */
export function useVerifyDecision(id: string) {
  return useQuery({
    queryKey: ["verify", id],
    queryFn: async () => (await api.get<VerifyResult>(`/decisions/${id}/verify`)).data,
    enabled: false,
    retry: false,
  });
}
