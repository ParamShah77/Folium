import * as React from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Coins, Landmark, Pencil, PlusCircle, Radio, Search, Sparkles, Trash2, Wallet } from "lucide-react";
import { PageHeader } from "@/components/layouts";
import { RupeeInput } from "@/components/profile-fields";
import { Button } from "@/components/ui/button";
import { Alert, Card, CardContent, CardDescription, CardHeader, CardTitle, Field, Input, Skeleton } from "@/components/ui/primitives";
import { Dialog, DialogContent, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/overlays";
import { api, errorMessage } from "@/lib/api";
import { usePortfolio } from "@/lib/queries";
import type { Holding, OtherAssets, PortfolioSummary } from "@/lib/types";
import { cn, formatINR, formatPct, formatPrice } from "@/lib/utils";

const ALLOC: { key: keyof PortfolioSummary["allocation"]; label: string; color: string }[] = [
  { key: "stocks", label: "Stocks", color: "bg-teal" },
  { key: "mutual_funds", label: "Mutual funds", color: "bg-bias-herd" },
  { key: "gold", label: "Gold", color: "bg-bias-disposition" },
  { key: "fixed_deposits", label: "Fixed deposits", color: "bg-sell" },
  { key: "savings", label: "Savings", color: "bg-sand" },
];

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["portfolio"] });
  };
}

/* ------------------------------------------------------------------ */
/* Summary                                                             */
/* ------------------------------------------------------------------ */

function Summary({ s }: { s: PortfolioSummary }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-3xl bg-teal-mist p-5">
          <p className="text-[13px] text-teal-ink">Net worth</p>
          <p className="tabular mt-2 font-serif text-[1.75rem] leading-none">{formatINR(s.net_worth)}</p>
          <p className="mt-2 text-xs text-muted-foreground">Everything you own, minus loans</p>
        </div>
        <div className="rounded-3xl border border-border bg-surface p-5 shadow-soft">
          <p className="text-[13px] text-muted-foreground">Liquid assets</p>
          <p className="tabular mt-2 font-serif text-[1.75rem] leading-none">{formatINR(s.liquid)}</p>
          <p className="mt-2 text-xs text-muted-foreground">Shares, funds, gold, FDs and savings</p>
        </div>
        <div className="rounded-3xl bg-blush p-5">
          <p className="text-[13px] text-rose">Monthly surplus</p>
          <p className="tabular mt-2 font-serif text-[1.75rem] leading-none">
            {s.monthly_surplus === null ? "—" : formatINR(s.monthly_surplus)}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">Income and rent in, fixed payments out</p>
        </div>
        <div className="rounded-3xl border border-border bg-surface p-5 shadow-soft">
          <p className="text-[13px] text-muted-foreground">Loans</p>
          <p className="tabular mt-2 font-serif text-[1.75rem] leading-none">{formatINR(s.liabilities)}</p>
          <p className="mt-2 text-xs text-muted-foreground">Home loan and other loans</p>
        </div>
      </div>

      {s.liquid > 0 && (
        <Card>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium">Where your money is</p>
              <p className="text-sm text-muted-foreground">
                {formatPct(s.equity_share, 0, false)} in shares and funds
              </p>
            </div>
            <div className="flex h-3 overflow-hidden rounded-full bg-surface-2" aria-hidden>
              {ALLOC.map((a) => (
                <span key={a.key} className={cn("h-full", a.color)} style={{ width: `${s.allocation[a.key].share * 100}%` }} />
              ))}
            </div>
            <ul className="grid gap-2 text-sm sm:grid-cols-3 lg:grid-cols-5">
              {ALLOC.map((a) => (
                <li key={a.key} className="flex items-center justify-between gap-2 rounded-2xl bg-surface-2/70 px-3.5 py-2.5">
                  <span className="flex items-center gap-2">
                    <span className={cn("size-2 rounded-full", a.color)} /> {a.label}
                  </span>
                  <span className="tabular text-muted-foreground">{formatINR(s.allocation[a.key].value)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Add / edit holding                                                  */
/* ------------------------------------------------------------------ */

function StockForm({ onDone }: { onDone: () => void }) {
  const invalidate = useInvalidate();
  const [symbol, setSymbol] = React.useState("");
  const [exchange, setExchange] = React.useState<"NSE" | "BSE">("NSE");
  const [qty, setQty] = React.useState("");
  const [avg, setAvg] = React.useState("");
  const [price, setPrice] = React.useState<number | null | undefined>(undefined);
  const [checking, setChecking] = React.useState(false);
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  async function check() {
    if (!symbol.trim()) return;
    setChecking(true);
    try {
      const { data } = await api.get("/portfolio/quote", { params: { symbol, exchange } });
      setPrice(data.quote?.price ?? null);
    } catch {
      setPrice(null);
    } finally {
      setChecking(false);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const q = Number(qty), a = Number(avg);
    if (!/^[A-Za-z0-9&.\-]{1,32}$/.test(symbol.trim())) return setError("Enter the stock's ticker, like RELIANCE");
    if (!(Number.isInteger(q) && q > 0)) return setError("Enter a whole number of shares");
    if (!(a > 0)) return setError("Enter the average price you paid per share");
    setBusy(true);
    setError(undefined);
    try {
      await api.post("/portfolio/holdings", { asset_type: "equity", symbol: symbol.trim().toUpperCase(), exchange, quantity: q, avg_buy_price: a });
      invalidate();
      toast.success(`${symbol.toUpperCase()} added`);
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-4" noValidate>
      {error && <Alert tone="danger">{error}</Alert>}
      <div className="grid grid-cols-[1fr_auto] gap-3">
        <Field id="h-symbol" label="Stock">
          <Input
            placeholder="RELIANCE"
            className="uppercase placeholder:normal-case"
            value={symbol}
            onChange={(e) => {
              setSymbol(e.target.value.toUpperCase());
              setPrice(undefined);
            }}
            onBlur={check}
          />
        </Field>
        <div className="space-y-1.5">
          <p className="text-sm font-medium">Exchange</p>
          <div className="flex h-11 rounded-xl bg-surface-2 p-1">
            {(["NSE", "BSE"] as const).map((x) => (
              <button
                key={x}
                type="button"
                aria-pressed={exchange === x}
                onClick={() => {
                  setExchange(x);
                  setPrice(undefined);
                }}
                className={cn("rounded-lg px-3 text-sm font-medium", exchange === x ? "bg-surface shadow-soft" : "text-muted-foreground")}
              >
                {x}
              </button>
            ))}
          </div>
        </div>
      </div>
      <p className="-mt-2 text-[13px] text-muted-foreground" aria-live="polite">
        {checking ? "Checking price…" : price === undefined ? " " : price === null ? "Live price unavailable right now. You can still add it." : (
          <span className="inline-flex items-center gap-1.5 text-success">
            <Radio className="size-3.5" /> Live price {formatPrice(price)}
          </span>
        )}
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Field id="h-qty" label="Shares">
          <Input inputMode="numeric" placeholder="120" value={qty} onChange={(e) => setQty(e.target.value.replace(/[^\d]/g, ""))} />
        </Field>
        <Field id="h-avg" label="Average buy price">
          <RupeeInput placeholder="1640" value={avg} onChange={(e) => setAvg(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
      </div>
      <Button type="submit" className="w-full" loading={busy}>
        Add stock
      </Button>
    </form>
  );
}

function FundForm({ onDone }: { onDone: () => void }) {
  const invalidate = useInvalidate();
  const [q, setQ] = React.useState("");
  const [debounced, setDebounced] = React.useState("");
  const [fund, setFund] = React.useState<{ scheme_code: string; name: string } | null>(null);
  const [units, setUnits] = React.useState("");
  const [avg, setAvg] = React.useState("");
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    const id = setTimeout(() => setDebounced(q.trim()), 350);
    return () => clearTimeout(id);
  }, [q]);

  const search = useQuery({
    queryKey: ["mf-search", debounced],
    enabled: debounced.length >= 3 && !fund,
    queryFn: async () => (await api.get<{ results: { scheme_code: string; name: string }[] }>("/portfolio/mf-search", { params: { q: debounced } })).data.results,
  });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!fund) return setError("Search for your fund and choose it from the list");
    if (!(Number(units) > 0)) return setError("Enter how many units you hold");
    if (!(Number(avg) > 0)) return setError("Enter your average purchase NAV");
    setBusy(true);
    setError(undefined);
    try {
      await api.post("/portfolio/holdings", {
        asset_type: "mf", scheme_code: fund.scheme_code, name: fund.name, quantity: Number(units), avg_buy_price: Number(avg),
      });
      invalidate();
      toast.success("Fund added");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-4" noValidate>
      {error && <Alert tone="danger">{error}</Alert>}
      {fund ? (
        <div className="flex items-start justify-between gap-3 rounded-2xl bg-teal-mist px-4 py-3">
          <p className="text-sm font-medium text-teal-ink">{fund.name}</p>
          <button type="button" className="shrink-0 text-xs text-primary hover:underline" onClick={() => setFund(null)}>
            Change
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <Field id="mf-q" label="Find your fund">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-subtle-foreground" />
              <Input className="pl-10" placeholder="Parag Parikh Flexi Cap" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
          </Field>
          <div className="max-h-48 overflow-y-auto rounded-2xl border border-border">
            {debounced.length < 3 ? (
              <p className="px-4 py-3 text-[13px] text-muted-foreground">Type at least 3 letters of the fund's name.</p>
            ) : search.isFetching ? (
              <p className="px-4 py-3 text-[13px] text-muted-foreground">Searching…</p>
            ) : search.data?.length ? (
              search.data.map((f) => (
                <button
                  key={f.scheme_code}
                  type="button"
                  onClick={() => setFund(f)}
                  className="block w-full border-b border-border px-4 py-2.5 text-left text-sm last:border-0 hover:bg-surface-2"
                >
                  {f.name}
                </button>
              ))
            ) : (
              <p className="px-4 py-3 text-[13px] text-muted-foreground">No funds found. Try a shorter name.</p>
            )}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field id="mf-units" label="Units">
          <Input inputMode="decimal" placeholder="152.347" value={units} onChange={(e) => setUnits(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
        <Field id="mf-avg" label="Average NAV paid">
          <RupeeInput placeholder="64.20" value={avg} onChange={(e) => setAvg(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
      </div>
      <Button type="submit" className="w-full" loading={busy}>
        Add fund
      </Button>
    </form>
  );
}

function EditHolding({ holding, onClose }: { holding: Holding; onClose: () => void }) {
  const invalidate = useInvalidate();
  const [qty, setQty] = React.useState(String(holding.quantity));
  const [avg, setAvg] = React.useState(String(holding.avg_buy_price));
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const base =
        holding.asset_type === "equity"
          ? { asset_type: "equity", symbol: holding.symbol, exchange: holding.exchange }
          : { asset_type: "mf", scheme_code: holding.scheme_code, name: holding.name };
      await api.put(`/portfolio/holdings/${holding.holding_id}`, { ...base, quantity: Number(qty), avg_buy_price: Number(avg) });
      invalidate();
      toast.success("Saved");
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-4" noValidate>
      {error && <Alert tone="danger">{error}</Alert>}
      <div className="grid grid-cols-2 gap-3">
        <Field id="e-qty" label={holding.asset_type === "mf" ? "Units" : "Shares"}>
          <Input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
        <Field id="e-avg" label="Average buy price">
          <RupeeInput value={avg} onChange={(e) => setAvg(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
      </div>
      <Button type="submit" className="w-full" loading={busy}>
        Save changes
      </Button>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Holdings                                                            */
/* ------------------------------------------------------------------ */

function Holdings({ holdings, liquid }: { holdings: Holding[]; liquid: number }) {
  const invalidate = useInvalidate();
  const [adding, setAdding] = React.useState(false);
  const [editing, setEditing] = React.useState<Holding | null>(null);

  async function remove(h: Holding) {
    if (!window.confirm(`Remove ${h.asset_type === "mf" ? h.name : h.symbol} from your portfolio?`)) return;
    try {
      await api.delete(`/portfolio/holdings/${h.holding_id}`);
      invalidate();
      toast.success("Removed");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>Shares and mutual funds</CardTitle>
          <CardDescription>The holdings you can analyse. Prices update during market hours.</CardDescription>
        </div>
        <Button size="sm" onClick={() => setAdding(true)}>
          <PlusCircle /> Add holding
        </Button>
      </CardHeader>
      <CardContent className="pt-4">
        {holdings.length === 0 ? (
          <div className="rounded-2xl bg-surface-2/70 px-6 py-10 text-center">
            <Wallet className="mx-auto size-6 text-primary" />
            <p className="mt-3 font-serif text-lg">Add your first holding</p>
            <p className="mt-1 text-sm text-muted-foreground">Start with the stock or fund you're thinking about.</p>
          </div>
        ) : (
          <div className="-mx-2 overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="text-left text-xs text-subtle-foreground">
                  <th className="px-2 py-2 font-medium">Holding</th>
                  <th className="px-2 py-2 text-right font-medium">Quantity</th>
                  <th className="px-2 py-2 text-right font-medium">Avg cost</th>
                  <th className="px-2 py-2 text-right font-medium">Price</th>
                  <th className="px-2 py-2 text-right font-medium">Value</th>
                  <th className="px-2 py-2 text-right font-medium">Gain / loss</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {holdings.map((h) => (
                  <tr key={h.holding_id}>
                    <td className="max-w-[16rem] px-2 py-3">
                      <p className="truncate font-medium">{h.asset_type === "mf" ? h.name : h.symbol}</p>
                      <p className="text-xs text-subtle-foreground">
                        {h.asset_type === "mf" ? "Mutual fund" : h.exchange} · {liquid > 0 ? formatPct(h.value / liquid, 1, false) : "—"} of liquid
                      </p>
                    </td>
                    <td className="tabular px-2 py-3 text-right">{h.quantity.toLocaleString("en-IN", { maximumFractionDigits: 3 })}</td>
                    <td className="tabular px-2 py-3 text-right">{formatPrice(h.avg_buy_price)}</td>
                    <td className="tabular px-2 py-3 text-right">
                      {h.current_price !== null ? formatPrice(h.current_price) : <span className="text-xs text-subtle-foreground">Unavailable</span>}
                    </td>
                    <td className="tabular px-2 py-3 text-right font-medium">{formatINR(h.value)}</td>
                    <td className={cn("tabular px-2 py-3 text-right", h.pnl === null ? "text-subtle-foreground" : h.pnl >= 0 ? "text-success" : "text-danger")}>
                      {h.pnl === null ? "—" : `${formatINR(h.pnl)} (${formatPct(h.pnl_pct)})`}
                    </td>
                    <td className="px-2 py-3">
                      <div className="flex justify-end gap-1">
                        <Button asChild size="sm" variant="soft">
                          <Link to={`/app/new?holding=${h.holding_id}`}>Analyse</Link>
                        </Button>
                        <Button size="icon" variant="ghost" aria-label="Edit" onClick={() => setEditing(h)}>
                          <Pencil />
                        </Button>
                        <Button size="icon" variant="ghost" aria-label="Remove" onClick={() => remove(h)}>
                          <Trash2 />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent title="Add a holding" description="Prices are looked up for you. Only the ticker or fund code leaves Folium.">
          <Tabs defaultValue="equity">
            <TabsList className="mb-5">
              <TabsTrigger value="equity">Stock</TabsTrigger>
              <TabsTrigger value="mf">Mutual fund</TabsTrigger>
            </TabsList>
            <TabsContent value="equity">
              <StockForm onDone={() => setAdding(false)} />
            </TabsContent>
            <TabsContent value="mf">
              <FundForm onDone={() => setAdding(false)} />
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(editing)} onOpenChange={(o) => !o && setEditing(null)}>
        {editing && (
          <DialogContent title={`Edit ${editing.asset_type === "mf" ? "fund" : editing.symbol}`}>
            <EditHolding holding={editing} onClose={() => setEditing(null)} />
          </DialogContent>
        )}
      </Dialog>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Other assets and liabilities                                        */
/* ------------------------------------------------------------------ */

const ASSET_FIELDS: { key: keyof OtherAssets; label: string; hint?: string; unit?: "g" }[] = [
  { key: "gold_grams", label: "Gold you own", hint: "Jewellery, coins and bars, in grams", unit: "g" },
  { key: "gold_buy_price_per_gram", label: "What you paid per gram", hint: "On average" },
  { key: "fixed_deposits", label: "Fixed deposits", hint: "Total value" },
  { key: "savings_balance", label: "Savings and cash" },
  { key: "real_estate_value", label: "Property value", hint: "Your own estimate" },
  { key: "home_loan_outstanding", label: "Home loan left to pay" },
  { key: "other_loans_outstanding", label: "Other loans left to pay", hint: "Car, personal, education" },
  { key: "rent_received", label: "Rent you receive", hint: "Per month" },
  { key: "monthly_sip", label: "Monthly investing (SIPs)", hint: "Per month, all schemes" },
];

function OtherAssetsCard({ assets, gold }: { assets: OtherAssets; gold: PortfolioSummary["gold"] }) {
  const invalidate = useInvalidate();
  const toForm = (a: OtherAssets) =>
    Object.fromEntries(ASSET_FIELDS.map((f) => [f.key, a[f.key] === null ? "" : String(a[f.key])])) as Record<keyof OtherAssets, string>;
  const [form, setForm] = React.useState(() => toForm(assets));
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => setForm(toForm(assets)), [assets]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.put(
        "/portfolio/assets",
        Object.fromEntries(ASSET_FIELDS.map((f) => [f.key, form[f.key] === "" ? null : Number(form[f.key])])),
      );
      invalidate();
      toast.success("Saved");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Landmark className="size-5 text-primary" /> Gold, deposits, property and loans
        </CardTitle>
        <CardDescription>All optional. They complete your net worth and monthly picture.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={save} className="space-y-5" noValidate>
          <div className="grid gap-5 sm:grid-cols-2">
            {ASSET_FIELDS.map((f) => (
              <Field key={f.key} id={`a-${f.key}`} label={f.label} hint={f.hint}>
                {f.unit === "g" ? (
                  <div className="relative">
                    <Input inputMode="decimal" placeholder="0" className="pr-10" value={form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.value.replace(/[^\d.]/g, "") })} />
                    <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">g</span>
                  </div>
                ) : (
                  <RupeeInput placeholder="0" value={form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.value.replace(/[^\d.]/g, "") })} />
                )}
              </Field>
            ))}
          </div>
          {gold.price_per_gram !== null && gold.price_source === "live" && (
            <p className="flex items-start gap-2 text-[13px] text-muted-foreground">
              <Coins className="mt-0.5 size-4 shrink-0 text-bias-disposition" />
              Gold is valued at {formatPrice(gold.price_per_gram)} per gram, the international price before Indian import
              duty and GST. Shop prices are usually higher.
            </p>
          )}
          <div className="flex justify-end">
            <Button type="submit" loading={busy}>
              Save
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function PortfolioPage() {
  const { data, isPending, isError } = usePortfolio();

  return (
    <>
      <PageHeader
        eyebrow="Portfolio"
        title="Your whole financial picture"
        description="Every analysis is judged against what you own and owe, so keep this up to date."
        actions={
          <Button asChild variant="outline">
            <Link to="/app/new">
              <Sparkles /> Analyse a decision
            </Link>
          </Button>
        }
      />
      {isPending ? (
        <div className="space-y-4">
          <Skeleton className="h-32 rounded-3xl" />
          <Skeleton className="h-64 rounded-3xl" />
        </div>
      ) : isError || !data ? (
        <Alert tone="danger">We couldn't load your portfolio. Refresh to try again.</Alert>
      ) : (
        <div className="space-y-6">
          <Summary s={data.summary} />
          <Holdings holdings={data.holdings} liquid={data.summary.liquid} />
          <OtherAssetsCard assets={data.assets} gold={data.summary.gold} />
          <p className="text-xs leading-relaxed text-subtle-foreground">
            Mutual funds are counted as shares when working out how much of your money is in the market. Your portfolio
            is private to your account.
          </p>
        </div>
      )}
    </>
  );
}
