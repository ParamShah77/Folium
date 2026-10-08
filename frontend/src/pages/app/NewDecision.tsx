import * as React from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, CircleMinus, CirclePlus, Clock, Info, PieChart, Radio, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { PageHeader } from "@/components/layouts";
import { RupeeInput } from "@/components/profile-fields";
import { Button } from "@/components/ui/button";
import { Alert, Card, CardContent, Field, Input, Skeleton, Textarea } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { useMarketContext, usePortfolio } from "@/lib/queries";
import type { Holding, Intent } from "@/lib/types";
import { cn, formatINR, formatPct, formatPrice } from "@/lib/utils";

const INTENTS: { value: Intent; label: string; hint: string; icon: React.ElementType }[] = [
  { value: "sell", label: "Sell", hint: "Exit some or all of it", icon: CircleMinus },
  { value: "hold", label: "Hold", hint: "Keep it as it is", icon: Clock },
  { value: "buy_more", label: "Buy more", hint: "Add to the position", icon: CirclePlus },
];

function MarketCard() {
  const { data, isPending } = useMarketContext();
  const live = data && data.market_data_source !== "unavailable";
  const trend = data?.market_trend;
  return (
    <div className="rounded-3xl bg-surface-2/70 p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Market right now</p>
        {live ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-success">
            <Radio className="size-3.5" /> Live
          </span>
        ) : (
          !isPending && <span className="text-xs text-muted-foreground">Unavailable</span>
        )}
      </div>
      {isPending ? (
        <div className="mt-4 space-y-2">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
        </div>
      ) : live ? (
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">NIFTY, 1 month</dt>
            <dd className={cn("tabular mt-0.5 flex items-center gap-1 font-medium", (data.nifty_1m_return ?? 0) >= 0 ? "text-success" : "text-danger")}>
              {(data.nifty_1m_return ?? 0) >= 0 ? <TrendingUp className="size-3.5" /> : <TrendingDown className="size-3.5" />}
              {formatPct(data.nifty_1m_return)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Market fear (VIX)</dt>
            <dd className="tabular mt-0.5 font-medium">{data.vix_value?.toFixed(2) ?? "—"}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-xs text-muted-foreground">Mood</dt>
            <dd className="mt-0.5 font-medium">{trend ? `${trend[0].toUpperCase()}${trend.slice(1)} market` : "—"}</dd>
          </div>
        </dl>
      ) : (
        <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
          Live market data couldn't be reached. The analysis will still run, assuming a calm market.
        </p>
      )}
      <p className="mt-4 text-xs leading-relaxed text-subtle-foreground">Saved with your decision so it can be reproduced exactly later.</p>
    </div>
  );
}

function HoldingPicker({ holdings, selected, onSelect, liquid }: { holdings: Holding[]; selected: string | null; onSelect: (id: string) => void; liquid: number }) {
  return (
    <div role="radiogroup" aria-label="Choose a holding" className="grid gap-3 sm:grid-cols-2">
      {holdings.map((h) => {
        const active = selected === h.holding_id;
        return (
          <button
            key={h.holding_id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onSelect(h.holding_id)}
            className={cn(
              "relative rounded-2xl border p-4 text-left transition-all",
              active ? "border-teal bg-teal-mist" : "border-border bg-surface hover:border-border-strong",
            )}
          >
            {active && <Check className="absolute right-3.5 top-3.5 size-4 text-primary" />}
            <p className={cn("truncate pr-6 font-medium", active && "text-teal-ink")}>{h.asset_type === "mf" ? h.name : h.symbol}</p>
            <p className="mt-0.5 text-xs text-subtle-foreground">
              {h.asset_type === "mf" ? "Mutual fund" : h.exchange} · {liquid > 0 ? formatPct(h.value / liquid, 0, false) : "—"} of your liquid assets
            </p>
            <div className="mt-3 flex items-baseline justify-between gap-2 text-sm">
              <span className="tabular font-medium">{formatINR(h.value)}</span>
              <span className={cn("tabular text-[13px]", h.pnl_pct === null ? "text-subtle-foreground" : h.pnl_pct >= 0 ? "text-success" : "text-danger")}>
                {h.pnl_pct === null ? "Price unavailable" : formatPct(h.pnl_pct)}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

export default function NewDecision() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const portfolio = usePortfolio();
  const holdings = portfolio.data?.holdings ?? [];
  const summary = portfolio.data?.summary;

  const [holdingId, setHoldingId] = React.useState<string | null>(params.get("holding"));
  const [intent, setIntent] = React.useState<Intent | null>(null);
  const [manualPrice, setManualPrice] = React.useState("");
  const [monthsHeld, setMonthsHeld] = React.useState("");
  const [reasoning, setReasoning] = React.useState("");
  const [errors, setErrors] = React.useState<{ holding?: string; intent?: string; price?: string }>({});
  const [submitError, setSubmitError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  const holding = holdings.find((h) => h.holding_id === holdingId) ?? null;
  const price = holding?.current_price ?? (manualPrice ? Number(manualPrice) : null);
  const value = holding && price ? holding.quantity * price : null;
  const pnlPct = holding && price ? price / holding.avg_buy_price - 1 : null;
  const share = value !== null && summary && summary.liquid > 0 ? value / summary.liquid : null;
  const months = monthsHeld === "" ? null : Number(monthsHeld);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs: typeof errors = {};
    if (!holding) errs.holding = "Choose the holding you're deciding about";
    if (!intent) errs.intent = "Choose what you're thinking of doing";
    if (holding && holding.current_price === null && !(Number(manualPrice) > 0)) errs.price = "Enter today's price";
    setErrors(errs);
    if (Object.keys(errs).length || !holding || !price) return;
    setBusy(true);
    setSubmitError(undefined);
    try {
      const { data } = await api.post<{ decision_id: string }>("/decisions/analyze", {
        holding_id: holding.holding_id,
        symbol: holding.symbol,
        exchange: holding.exchange,
        holding_quantity: holding.quantity,
        avg_buy_price: holding.avg_buy_price,
        current_price: price,
        unrealized_pnl_pct: Math.round((price / holding.avg_buy_price - 1) * 10000) / 10000,
        decision_intent: intent,
        holding_period_days: months === null ? null : Math.round(months * 30.44),
        user_reasoning: reasoning.trim() || null,
      });
      qc.invalidateQueries({ queryKey: ["decisions"] });
      navigate(`/app/decisions/${data.decision_id}`);
    } catch (err) {
      setSubmitError(errorMessage(err));
      setBusy(false);
    }
  }

  if (portfolio.isPending) {
    return <Skeleton className="h-96 rounded-3xl" />;
  }

  if (holdings.length === 0) {
    return (
      <>
        <PageHeader eyebrow="New analysis" title="First, add what you own" />
        <Card>
          <CardContent className="flex flex-col items-center px-8 py-14 text-center">
            <span className="flex size-14 items-center justify-center rounded-3xl bg-teal-mist text-primary">
              <Wallet className="size-6" />
            </span>
            <h2 className="mt-5 text-2xl">Folium judges each decision against your whole portfolio</h2>
            <p className="mt-2 max-w-md leading-relaxed text-muted-foreground">
              Add the shares and mutual funds you hold, and optionally your gold, deposits, property and loans. It takes a
              few minutes and you only do it once.
            </p>
            <Button asChild size="lg" className="mt-7">
              <Link to="/app/portfolio">
                Set up your portfolio <ArrowRight />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="New analysis"
        title="What are you thinking of doing?"
        description="Pick a holding and your instinct. Folium checks the moment for bias and weighs both paths against your whole portfolio, up to when you need the money."
      />

      <form onSubmit={onSubmit} noValidate className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          {submitError && <Alert tone="danger">{submitError}</Alert>}

          <Card>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-serif text-lg">Which holding?</p>
                <Link to="/app/portfolio" className="text-[13px] text-primary hover:underline">
                  Manage portfolio
                </Link>
              </div>
              {errors.holding && <p className="text-[13px] text-danger">{errors.holding}</p>}
              <HoldingPicker
                holdings={holdings}
                selected={holdingId}
                onSelect={(id) => {
                  setHoldingId(id);
                  setErrors((e) => ({ ...e, holding: undefined, price: undefined }));
                }}
                liquid={summary?.liquid ?? 0}
              />
              {holding && holding.current_price === null && (
                <Field id="price" label="Today's price" hint="We couldn't fetch a live price. Enter it to continue." error={errors.price} className="sm:max-w-64">
                  <RupeeInput value={manualPrice} onChange={(e) => setManualPrice(e.target.value.replace(/[^\d.]/g, ""))} />
                </Field>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-5">
              <div>
                <p className="font-serif text-lg">Your instinct</p>
                {errors.intent && <p className="mt-1 text-[13px] text-danger">{errors.intent}</p>}
              </div>
              <div role="radiogroup" aria-label="What you're considering" className="grid gap-3 sm:grid-cols-3">
                {INTENTS.map(({ value: v, label, hint, icon: Icon }) => {
                  const active = intent === v;
                  return (
                    <button
                      key={v}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => {
                        setIntent(v);
                        setErrors((e) => ({ ...e, intent: undefined }));
                      }}
                      className={cn("relative rounded-2xl border p-4 text-left transition-all", active ? "border-teal bg-teal-mist" : "border-border hover:border-border-strong")}
                    >
                      {active && <Check className="absolute right-3.5 top-3.5 size-4 text-primary" />}
                      <Icon className={cn("size-5", active ? "text-primary" : "text-subtle-foreground")} />
                      <p className={cn("mt-3 font-medium", active && "text-teal-ink")}>{label}</p>
                      <p className="text-[13px] text-muted-foreground">{hint}</p>
                    </button>
                  );
                })}
              </div>
              <div className="grid gap-5 sm:grid-cols-[1fr_180px]">
                <Field id="reasoning" label="Why? In your own words" hint="Optional, but useful when you look back later.">
                  <Textarea placeholder="It's been falling for weeks and everyone in my group is getting out…" value={reasoning} maxLength={2000} onChange={(e) => setReasoning(e.target.value)} />
                </Field>
                <Field id="months" label="Months held" hint="Optional. Sets short- or long-term tax.">
                  <Input inputMode="numeric" placeholder="14" value={monthsHeld} onChange={(e) => setMonthsHeld(e.target.value.replace(/[^\d]/g, ""))} />
                </Field>
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <Card>
            <CardContent>
              <p className="flex items-center gap-2 text-sm font-medium">
                <PieChart className="size-4 text-primary" /> In your portfolio
              </p>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Value today</dt>
                  <dd className="tabular font-medium">{formatINR(value)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Gain or loss</dt>
                  <dd className={cn("tabular font-medium", pnlPct === null ? "" : pnlPct >= 0 ? "text-success" : "text-danger")}>{formatPct(pnlPct)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Share of liquid assets</dt>
                  <dd className="tabular font-medium">{share === null ? "—" : formatPct(share, 1, false)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Monthly surplus</dt>
                  <dd className="tabular font-medium">{summary?.monthly_surplus == null ? "—" : formatINR(summary.monthly_surplus)}</dd>
                </div>
                {holding && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Price</dt>
                    <dd className="tabular font-medium">{price ? formatPrice(price) : "—"}</dd>
                  </div>
                )}
              </dl>
              <Button type="submit" size="lg" className="mt-6 w-full" loading={busy}>
                Analyse decision <ArrowRight />
              </Button>
              <p className="mt-3 flex items-start gap-1.5 text-xs leading-relaxed text-subtle-foreground">
                <Info className="mt-0.5 size-3.5 shrink-0" /> Takes about 10 seconds. Not investment advice.
              </p>
            </CardContent>
          </Card>
          <MarketCard />
        </aside>
      </form>
    </>
  );
}
