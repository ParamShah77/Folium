import * as React from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CircleAlert,
  CircleCheck,
  Download,
  FlaskConical,
  Languages,
  Lightbulb,
  ListChecks,
  PieChart,
  PlusCircle,
  Quote,
  ShieldCheck,
  Fingerprint,
} from "lucide-react";
import { PageHeader } from "@/components/layouts";
import { BiasBadge, PipelineTimeline, WealthFanChart, useDecisionStream } from "@/components/decision";
import { Button } from "@/components/ui/button";
import { Alert, Badge, Card, CardContent, CardDescription, CardHeader, CardTitle, Skeleton } from "@/components/ui/primitives";
import { BIAS_META, BIAS_ORDER, INTENT_LABEL, VERDICT_META, confidenceLevel, decisionTitle } from "@/lib/domain";
import { useDecision, useVerifyDecision } from "@/lib/queries";
import type { BiasType, Decision } from "@/lib/types";
import { cn, formatDate, formatINR, formatPct, formatPrice } from "@/lib/utils";

const FIELD_LABELS: Record<string, string> = {
  age: "age",
  risk_tolerance: "comfort with risk",
  investment_horizon: "horizon",
  monthly_income: "monthly income",
  monthly_expense: "monthly payments",
  has_emergency_fund: "emergency fund",
  financial_strategy: "investing style",
  goal: "goal",
  position_size_pct: "position size",
  years_investing: "years of investing",
  investment_experience: "investing experience",
  position_share: "position size",
  asset_mix: "mix of shares, funds and gold",
  liquid_assets: "savings and investments",
  property_loans: "property and loans",
  holding_period: "how long you've held it",
  portfolio: "the rest of your portfolio",
  monthly_sip: "monthly investing",
  stock_risk: "how this stock usually moves",
};

const DEST_LABEL: Record<string, string> = { fixed_deposits: "fixed deposits", gold: "gold", savings: "savings" };

/** "60% into fixed deposits, 20% into gold and 20% into savings" */
function destinationText(dest: Record<string, number>): string {
  const parts = Object.entries(dest)
    .filter(([, w]) => w > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([k, w]) => `${Math.round(w * 100)}% into ${DEST_LABEL[k] ?? k}`);
  if (parts.length <= 1) return parts[0] ?? "";
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function horizonPhrase(years: number): string {
  return years === 1 ? "1 year" : `${years} years`;
}

/* ------------------------------------------------------------------ */
/* While the analysis runs                                             */
/* ------------------------------------------------------------------ */

function LiveView({ decision }: { decision: Decision }) {
  const stream = useDecisionStream(decision.decision_id, true);
  useDecision(decision.decision_id, { poll: stream.connection === "fallback" });
  const share = decision.portfolio_context?.position_share;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        eyebrow="Analysing"
        title={
          <>
            {decisionTitle(decision)} <span className="text-muted-foreground">· {INTENT_LABEL[decision.decision_intent]}</span>
          </>
        }
        description="This usually takes about ten seconds."
      />
      <div className="grid gap-6 md:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardContent className="p-7">
            <PipelineTimeline stream={stream} />
          </CardContent>
        </Card>
        <div className="space-y-4">
          <div className="rounded-3xl bg-teal-mist p-6">
            <p className="text-[13px] text-teal-ink/80">This position</p>
            <p className="tabular mt-1 font-serif text-2xl text-teal-ink">{formatINR(decision.holding_quantity * decision.current_price)}</p>
            <p className={cn("tabular mt-1 text-sm", decision.unrealized_pnl_pct >= 0 ? "text-success" : "text-danger")}>
              {formatPct(decision.unrealized_pnl_pct)} since you bought
            </p>
            {share != null && <p className="mt-1 text-sm text-teal-ink/80">{formatPct(share, 0, false)} of your liquid assets</p>}
          </div>
          {decision.user_reasoning && (
            <div className="rounded-3xl bg-blush p-6">
              <Quote className="size-4 text-rose" />
              <p className="mt-2 font-serif leading-snug text-rose">{decision.user_reasoning}</p>
            </div>
          )}
          {stream.terminal === "timeout" && <Alert tone="warning">The live feed timed out. Your result will appear here as soon as it's ready.</Alert>}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Result                                                              */
/* ------------------------------------------------------------------ */

function VerdictHero({ d }: { d: Decision }) {
  const verdict = d.recommendation;
  const reasons = d.debate_transcript?.reasons ?? [];
  const agrees =
    (verdict === "SELL" && d.decision_intent === "sell") ||
    (verdict === "HOLD" && d.decision_intent === "hold") ||
    (verdict === "BUY_MORE" && d.decision_intent === "buy_more");
  return (
    <div className="relative overflow-hidden rounded-[2rem] bg-teal-mist p-7 sm:p-9">
      <div className="absolute -right-16 -top-20 size-64 rounded-full bg-blush/70 blur-3xl" aria-hidden />
      <div className="relative grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-end">
        <div>
          <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-teal-ink/80">Our read</p>
          <p className="mt-3 font-serif text-5xl leading-none text-teal-ink">{verdict ? VERDICT_META[verdict].label : "—"}</p>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-teal-ink/85">
            {agrees
              ? "The evidence supports what you were planning to do."
              : `You were leaning towards ${INTENT_LABEL[d.decision_intent].toLowerCase()}. The evidence points the other way.`}
          </p>
        </div>
        <ul className="space-y-2.5">
          {reasons.map((r) => (
            <li key={r} className="flex gap-2.5 rounded-2xl bg-surface/75 px-4 py-3 text-sm leading-relaxed backdrop-blur">
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-primary" />
              {r}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function SimulationCard({ d }: { d: Decision }) {
  const c = d.simulation_curves;
  if (!c) return null;
  const opp = d.opportunity_cost_inr ?? 0;
  const horizon = c.horizon_years ?? 20;
  const sale = c.sale;
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="font-serif text-xl">{horizonPhrase(horizon)} from now</CardTitle>
          <CardDescription>
            {c.n_paths.toLocaleString("en-IN")} possible futures for this position
            {c.horizon_source === "profile" && ", up to when you need the money"}
            {c.horizon_source === "default" && (
              <>
                {" "}· a standard 20-year view.{" "}
                <Link to="/app/settings" className="text-primary hover:underline">Add your time horizon</Link>
              </>
            )}
          </CardDescription>
        </div>
        <div className="flex gap-4 text-[13px] text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-hold" /> Hold</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-sell" /> Sell</span>
        </div>
      </CardHeader>
      <CardContent>
        <WealthFanChart curves={c} />
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl bg-hold-mist px-4 py-3.5">
            <p className="text-xs text-teal-ink">If you hold, most likely{sale ? ", after tax" : ""}</p>
            <p className="tabular mt-1 font-serif text-2xl">{formatINR(d.hold_median_20y)}</p>
            <p className="tabular text-xs text-muted-foreground">{formatINR(d.hold_p10_20y)} if things go badly</p>
          </div>
          <div className="rounded-2xl bg-sell-mist px-4 py-3.5">
            <p className="text-xs text-muted-foreground">If you sell, most likely{sale ? ", after tax" : ""}</p>
            <p className="tabular mt-1 font-serif text-2xl">{formatINR(d.sell_median_20y)}</p>
            <p className="tabular text-xs text-muted-foreground">{formatINR(d.sell_p10_20y)} if things go badly</p>
          </div>
          <div className="rounded-2xl bg-surface-2 px-4 py-3.5">
            <p className="text-xs text-muted-foreground">Staying invested wins</p>
            <p className="tabular mt-1 font-serif text-2xl">{Math.round(c.prob_hold_better * 100)}%</p>
            <p className="text-xs text-muted-foreground">of the time</p>
          </div>
        </div>
        {sale ? (
          <div className="mt-5 space-y-2 text-sm leading-relaxed text-muted-foreground">
            <p>
              Typically, {opp >= 0 ? "selling now leaves you" : "holding leaves you"}{" "}
              <span className="font-medium text-orange-ink">{formatINR(Math.abs(opp))}</span> worse off after{" "}
              {horizonPhrase(horizon)}, after tax.
            </p>
            <p>
              Selling today costs {formatINR(sale.costs)} in charges
              {sale.tax >= 1
                ? ` and ${formatINR(sale.tax)} in ${sale.tax_kind === "short_term" ? "short-term" : "long-term"} capital-gains tax`
                : sale.gain > 0
                  ? " (no tax: long-term gains up to ₹1.25 lakh a year are tax-free)"
                  : " (no tax on a loss)"}
              , leaving {formatINR(sale.proceeds)}. That goes where your safer money already is:{" "}
              {destinationText(sale.destination)}.
            </p>
            {c.holding_risk?.asset_type === "equity" && (
              <p>
                {c.holding_risk.source === "measured" ? "Over the past 10 years this stock moved" : "A typical large stock moves"}{" "}
                about {c.holding_risk.beta.toFixed(2)}× as much as NIFTY, plus around{" "}
                {Math.round(c.holding_risk.specific_vol * 100)}% a year of swings of its own, which is why a single stock's
                range of outcomes is wider than a fund's.
              </p>
            )}
            <p className="text-xs text-subtle-foreground">
              Amounts are what you'd have in hand after tax and charges if you cashed in that year.
            </p>
          </div>
        ) : (
          <p className="mt-5 text-sm leading-relaxed text-muted-foreground">
            On average, {opp >= 0 ? "selling now gives up" : "holding gives up"}{" "}
            <span className="font-medium text-orange-ink">{formatINR(Math.abs(opp))}</span> over 20 years. After selling, the
            money is assumed to move to a safer mix ({Math.round(c.sell_stock_allocation * 100)}% in shares, against{" "}
            {Math.round(c.hold_stock_allocation * 100)}%{c.allocation_basis === "portfolio" ? ", your current mix," : ""} if you hold).
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function BiasCard({ d }: { d: Decision }) {
  const bias = d.bias_detected;
  if (!bias) return null;
  const probs = d.explainer_output?.bias?.probabilities ?? {};
  const actionAware = d.explainer_output?.bias?.model === "bias_v4";
  const modelKey: Record<BiasType, string> = { loss_aversion: "loss_aversion", herd_behavior: "herd", disposition_effect: "disposition", rational: "rational" };
  const level = confidenceLevel(d.bias_confidence);
  return (
    <Card>
      <CardHeader>
        <CardDescription>What we noticed</CardDescription>
        <CardTitle className="font-serif text-2xl">{BIAS_META[bias].label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <p className="text-sm leading-relaxed text-muted-foreground">{BIAS_META[bias].description}</p>
        <Badge tone={level.tone === "high" ? "teal" : level.tone === "medium" ? "warning" : "neutral"} className="px-3 py-1 text-[13px]">
          {level.label}
        </Badge>
        <div>
          <p className="mb-3 text-[13px] text-muted-foreground">
            How closely your {actionAware ? "decision" : "situation"} matches each pattern
          </p>
          <ul className="space-y-2.5">
            {BIAS_ORDER.map((b) => {
              const p = probs[modelKey[b]] ?? 0;
              return (
                <li key={b} className="space-y-1 text-[13px]">
                  <span className={cn(b === bias ? "font-medium text-foreground" : "text-muted-foreground")}>{BIAS_META[b].label}</span>
                  <span className="block h-1.5 overflow-hidden rounded-full bg-surface-2">
                    <span className={cn("block h-full rounded-full", BIAS_META[b].dot)} style={{ width: `${Math.max(p * 100, 2)}%`, opacity: b === bias ? 1 : 0.5 }} />
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

function ExplanationCard({ d }: { d: Decision }) {
  const out = d.explainer_output;
  const [lang, setLang] = React.useState<"en" | "hi">("en");
  const gap = out?.explanation?.[lang];

  if (!gap) {
    if (!out?.story?.length) return null;
    return (
      <Card>
        <CardHeader>
          <CardDescription className="flex items-center gap-1.5">
            <Lightbulb className="size-4 text-peach" /> The explanation
          </CardDescription>
          <CardTitle className="font-serif text-2xl">{out.headline}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {out.story.map((s) => (
            <div key={s.title}>
              <p className="font-medium">{s.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  const report = (format: "html" | "pdf") => `/v1/decisions/${d.decision_id}/report?format=${format}&lang=${lang}`;
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardDescription className="flex items-center gap-1.5">
            <Lightbulb className="size-4 text-peach" /> The explanation
          </CardDescription>
          <CardTitle className="font-serif text-2xl">{lang === "en" ? "What this means for you" : "आपके लिए इसका मतलब"}</CardTitle>
        </div>
        <div className="flex items-center gap-1 rounded-full bg-surface-2 p-1" role="group" aria-label="Language">
          <Languages className="ml-2 size-4 text-subtle-foreground" aria-hidden />
          {(["en", "hi"] as const).map((l) => (
            <button
              key={l}
              type="button"
              aria-pressed={lang === l}
              onClick={() => setLang(l)}
              className={cn("rounded-full px-3 py-1 text-sm transition-all", lang === l ? "bg-surface font-medium shadow-soft" : "text-muted-foreground")}
            >
              {l === "en" ? "English" : "हिंदी"}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <ol className="space-y-6" lang={lang}>
          {gap.sections.map((s, i) => (
            <li key={s.key} className="flex gap-4">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-medium text-primary">{i + 1}</span>
              <div className="min-w-0">
                <p className="font-medium">{s.title}</p>
                <div className="mt-1.5 space-y-2.5 text-sm leading-relaxed text-muted-foreground">
                  {s.text.split(/\n\n+/).map((para, pi) =>
                    para.trim().startsWith("|") ? (
                      <MarkdownTable key={pi} text={para} />
                    ) : (
                      <p key={pi} className="whitespace-pre-line">{para.replace(/\*\*/g, "")}</p>
                    ),
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-7 flex flex-wrap items-center gap-2 border-t border-border pt-5">
          <span className="mr-1 text-sm text-muted-foreground">Keep a copy</span>
          <Button asChild size="sm" variant="outline">
            <a href={report("html")} download>
              <Download /> Report (HTML)
            </a>
          </Button>
          {lang === "en" ? (
            <Button asChild size="sm" variant="outline">
              <a href={report("pdf")} download>
                <Download /> Report (PDF)
              </a>
            </Button>
          ) : (
            <span className="text-xs text-subtle-foreground">For a Hindi PDF, open the HTML report and print it to PDF.</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/** The explanation's year-by-year table arrives as a small markdown table. */
function MarkdownTable({ text }: { text: string }) {
  const rows = text
    .trim()
    .split("\n")
    .filter((l) => !/^\s*\|?\s*:?-{2,}/.test(l))
    .map((l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim().replace(/\*\*/g, "")));
  if (rows.length < 2) return null;
  const [head, ...body] = rows;
  return (
    <div className="overflow-x-auto rounded-2xl border border-border">
      <table className="w-full text-[13px]">
        <thead className="bg-surface-2/70">
          <tr>{head.map((h) => <th key={h} className="px-3 py-2 text-left font-medium text-foreground">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-border">
          {body.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j} className="tabular px-3 py-2">{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SignalsCard({ d }: { d: Decision }) {
  const factors = d.explainer_output?.factors ?? [];
  if (!factors.length) return null;
  const max = Math.max(...factors.map((f) => Math.abs(f.shap_impact)), 1e-6);
  // Only v4 explains the pattern it chose, so only v4's direction is shown.
  const signed = factors.some((f) => f.direction === "toward" || f.direction === "against");
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center gap-1.5">
          <ListChecks className="size-4 text-primary" /> Behind the call
        </CardDescription>
        <CardTitle>What weighed most</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-4">
          {factors.map((f, i) => {
            const share = Math.abs(f.shap_impact) / max;
            const against = signed && f.direction === "against";
            return (
              <li key={f.feature}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span>{f.label}</span>
                  <span className="shrink-0 text-xs text-subtle-foreground">
                    {signed ? (against ? "Pointed away" : "Pointed toward") : `#${i + 1}`}
                  </span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className={cn("h-full rounded-full", against ? "bg-sell" : "bg-teal")}
                    style={{ width: `${share * 100}%`, opacity: 0.45 + share * 0.55 }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
        <p className="mt-5 text-xs leading-relaxed text-subtle-foreground">
          {signed
            ? "Longer bars mattered more. Teal pointed toward this reading; grey pointed away from it."
            : "Longer bars mattered more in this particular read."}
        </p>
      </CardContent>
    </Card>
  );
}

function PortfolioCard({ d }: { d: Decision }) {
  const p = d.portfolio_context;
  if (!p) return null;
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center gap-1.5">
          <PieChart className="size-4 text-primary" /> Against your whole portfolio
        </CardDescription>
        <CardTitle>How big this decision is</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["This position", formatINR(p.position_value), p.position_share != null ? `${formatPct(p.position_share, 1, false)} of liquid assets` : ""],
            ["Net worth", formatINR(p.net_worth), "Everything you own, minus loans"],
            ["Monthly surplus", p.monthly_surplus == null ? "—" : formatINR(p.monthly_surplus), "After fixed payments"],
            ["In shares and funds", formatPct(p.equity_share, 0, false), "Of your liquid assets"],
          ].map(([label, value, hint]) => (
            <div key={label} className="rounded-2xl bg-surface-2/70 px-4 py-3.5">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="tabular mt-1 font-serif text-xl">{value}</dd>
              <dd className="text-xs text-subtle-foreground">{hint}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

function CausalCard({ d }: { d: Decision }) {
  const c = d.explainer_output?.causal;
  if (!c || (!c.primary && !c.intervention)) return null;
  const iv = c.intervention;
  const verb: Record<string, string> = { sell: "sell", hold: "hold on", buy_more: "buy more" };
  const ivVerb = verb[iv?.action ?? "sell"] ?? "sell";
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center gap-1.5">
          <FlaskConical className="size-4 text-primary" /> Cause and effect
        </CardDescription>
        <CardTitle className="font-serif text-xl">What pushes a decision like this, and what helps</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        <div className="space-y-4">
          {c.primary && (
            <div className="rounded-2xl bg-surface-2/70 p-5">
              {c.primary.situation && c.primary.share_taking_action != null ? (
                <p className="text-sm text-muted-foreground">
                  {c.primary.situation}, about {Math.round(c.primary.share_taking_action * 100)}% of investors{" "}
                  {verb[c.primary.action ?? "sell"]}. A stronger tendency towards this pattern
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">Across many investors, this pattern</p>
              )}
              <p className="mt-1 font-serif text-2xl">
                {c.primary.effect > 0 ? "raises" : "lowers"} the chance of {c.primary.action_words ?? "selling"}
              </p>
              <div className="mt-4">
                <Badge tone={c.primary.refutation_passed ? "success" : "warning"}>
                  {c.primary.refutation_passed ? "Holds up when checked against chance" : "Not fully confirmed yet"}
                </Badge>
              </div>
            </div>
          )}
          {c.context.length > 0 && (
            <ul className="space-y-2 text-sm">
              {c.context.map((e) => (
                <li key={e.treatment} className="flex justify-between gap-3">
                  <span className="text-muted-foreground">{e.label}</span>
                  <span className="font-medium">{e.effect > 0 ? "makes selling likelier" : "makes selling less likely"}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        {iv && (
          <div className="rounded-2xl bg-blush/60 p-5 dark:bg-blush">
            <p className="text-sm font-medium text-rose">What helps</p>
            <p className="mt-1 font-serif text-lg leading-snug">{iv.description}</p>
            <div className="mt-5 space-y-3 text-sm">
              {([
                ["Usually", iv.original_sell_prob, "bg-sell"],
                ["With this habit", iv.new_sell_prob, "bg-teal"],
              ] as const).map(([label, p, color]) => (
                <div key={label}>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="tabular font-medium">{Math.round(p * 100)}% would {ivVerb}</span>
                  </div>
                  <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface/70">
                    <div className={cn("h-full rounded-full", color)} style={{ width: `${p * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
            {iv.assumption && (
              <p className="mt-4 text-xs leading-relaxed text-subtle-foreground">
                Among investors in a situation like yours. Assumes the habit halves the tendency it works on.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const FACT_LABEL: Record<string, string> = {
  cash_need: "You need the money",
  rebalance: "Too much in one holding",
  goal_near: "A goal is close",
};

/** Phase B3: the investor's comment, what it says, and how it lines up with the reading. */
function OwnWordsCard({ d }: { d: Decision }) {
  const w = d.explainer_output?.own_words;
  return (
    <div className="rounded-3xl bg-blush/70 p-6 dark:bg-blush">
      <p className="flex items-center gap-1.5 text-sm text-rose">
        <Quote className="size-4" /> In your own words
      </p>
      <p className="mt-2 font-serif text-lg leading-snug">{d.user_reasoning}</p>
      {w && (w.facts.length > 0 || w.cues.length > 0) && (
        <div className="mt-5 space-y-3 text-sm">
          {w.facts.map((f) => (
            <p key={f.kind + f.quote} className="leading-relaxed">
              <span className="font-medium">{FACT_LABEL[f.kind] ?? f.kind}</span>
              <span className="text-muted-foreground"> · "{f.quote}"</span>
              {f.kind === "cash_need" && (
                <span className="block text-xs text-muted-foreground">Taken into account in the pattern reading.</span>
              )}
            </p>
          ))}
          {Object.entries(
            w.cues.reduce<Record<string, string[]>>((byQuote, c) => {
              (byQuote[c.quote] ??= []).push(c.label);
              return byQuote;
            }, {}),
          ).map(([quote, labels]) => (
            <p key={quote} className="leading-relaxed">
              <span className="font-medium">Sounds like {labels.join(" and ")}</span>
              <span className="text-muted-foreground"> · "{quote}"</span>
            </p>
          ))}
          {w.note && (
            <p className={cn("rounded-2xl px-4 py-3 leading-relaxed", w.agreement === "differs" ? "bg-surface/80" : "bg-surface/50")}>
              {w.note}
            </p>
          )}
          <p className="text-xs text-subtle-foreground">
            Feelings are shown back to you; only a stated need for the money changes the reading.
            {w.source === "rules+gemini" ? " Read with AI help, which you turned on." : ""}
          </p>
        </div>
      )}
    </div>
  );
}

/** Phase B3: the strongest reasons on both sides, built from this analysis's numbers. */
function BothSidesCard({ d }: { d: Decision }) {
  const cases = d.debate_transcript?.cases?.filter((c) => c.text);
  if (!cases?.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardDescription>Before you decide</CardDescription>
        <CardTitle className="font-serif text-xl">Both sides, in numbers</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        {cases.map((c) => (
          <div key={c.side} className={cn("rounded-2xl p-5", c.side === "stay" ? "bg-hold-mist" : "bg-sell-mist")}>
            <p className={cn("font-medium", c.side === "stay" ? "text-teal-ink" : "text-foreground")}>{c.title}</p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{c.text}</p>
          </div>
        ))}
        <p className="text-xs text-subtle-foreground md:col-span-2">
          These set out both sides; they don't change our read above.
          {d.debate_transcript?.llm_debate ? " Worded with AI help, checked so no number was added or changed." : ""}
        </p>
      </CardContent>
    </Card>
  );
}

/** "Verify this record": the analysis against its sealed entry in the investor's chain (Phase B1). */
function SecureRecordCard({ d }: { d: Decision }) {
  const verify = useVerifyDecision(d.decision_id);
  const v = verify.data;
  const short = (h?: string) => (h ? `${h.slice(0, 8)}…${h.slice(-8)}` : "");
  let tone: "success" | "warning" | null = null;
  let message = "";
  if (v) {
    const n = v.chain.entries;
    const chainText = `all ${n} record${n === 1 ? "" : "s"} in your chain ${n === 1 ? "is" : "are"} intact`;
    if (!v.chain.valid) {
      tone = "warning";
      message = `Your record chain has a problem: ${v.chain.problems[0]?.detail ?? "it doesn't check out"}.`;
    } else if (v.record.status === "verified") {
      tone = "success";
      message = `Verified. This analysis matches the secure record made on ${formatDate(v.record.recorded_at ?? d.submitted_at, true)}, and ${chainText}.`;
    } else if (v.record.status === "matches_earlier_format") {
      tone = "success";
      message = `Verified in the earlier record format: the pattern and recommendation match what was recorded, and ${chainText}.`;
    } else if (v.record.status === "changed") {
      tone = "warning";
      message = `This analysis has changed since it was recorded: ${(v.record.changed ?? ["the analysis"]).join(" and ")}.`;
    } else {
      tone = "warning";
      message = "No secure record was found for this analysis.";
    }
  }
  return (
    <Card>
      <CardContent className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <Fingerprint className="mt-0.5 size-5 shrink-0 text-primary" />
          <div className="space-y-1">
            <p className="font-medium">Secure record</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Every analysis is sealed into your own record chain when it's made, so it can't be quietly changed later.
            </p>
            {v && (
              <p className={cn("text-sm leading-relaxed", tone === "success" ? "text-teal-ink" : "text-rose")} role="status">
                {message}
              </p>
            )}
            {v?.record.fingerprint && (
              <p className="tabular text-xs text-subtle-foreground">Record fingerprint {short(v.record.fingerprint)}</p>
            )}
            {verify.isError && <p className="text-sm text-rose">Couldn't check the record just now. Try again.</p>}
          </div>
        </div>
        <Button variant="outline" onClick={() => verify.refetch()} disabled={verify.isFetching} className="shrink-0">
          {verify.isFetching ? "Checking…" : v ? "Check again" : "Verify this record"}
        </Button>
      </CardContent>
    </Card>
  );
}

function Methodology({ d }: { d: Decision }) {
  const bias = d.explainer_output?.bias;
  const assumed = bias?.assumed_defaults ?? [];
  const fixed = [...new Set([...(bias?.fixed_inputs ?? []), ...(d.simulation_curves?.fixed_inputs ?? [])])];
  const horizon = d.simulation_curves?.horizon_years ?? 20;
  return (
    <details className="group rounded-3xl border border-border bg-surface px-6 py-5 shadow-soft">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-medium">
        <span className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" /> How this was worked out
        </span>
        <span className="text-sm text-muted-foreground group-open:hidden">Show</span>
        <span className="hidden text-sm text-muted-foreground group-open:inline">Hide</span>
      </summary>
      <div className="mt-5 grid gap-6 text-sm leading-relaxed text-muted-foreground md:grid-cols-3">
        <div className="space-y-2">
          <p className="font-medium text-foreground">The market</p>
          {d.market_data_source && d.market_data_source !== "unavailable" ? (
            <p>
              NIFTY had moved {formatPct(d.nifty_1m_return)} over the past month, market fear (India VIX) was at{" "}
              {d.vix_value ?? "—"}, and the mood was {d.market_trend ?? "unclear"}. These were saved when you asked.
            </p>
          ) : (
            <p>Live market data wasn't available, so a calm market was assumed.</p>
          )}
        </div>
        <div className="space-y-2">
          <p className="font-medium text-foreground">You and your portfolio</p>
          <p>
            {d.portfolio_context
              ? "Your profile and saved portfolio were used, including this holding's real share of your money."
              : "Your saved profile was used."}
          </p>
          {assumed.length > 0 && (
            <p>
              Typical values filled in for your {assumed.map((a) => FIELD_LABELS[a] ?? a).join(", ")}.{" "}
              <Link to="/app/settings" className="text-primary hover:underline">Complete your profile</Link>
            </p>
          )}
          {fixed.length > 0 && <p>Standard values used for your {fixed.map((a) => FIELD_LABELS[a] ?? a).join(" and ")}.</p>}
        </div>
        <div className="space-y-2">
          <p className="font-medium text-foreground">The reasoning</p>
          {bias?.model === "bias_v4" ? (
            <p>
              What you chose to do, in this market and with this portfolio, is compared with 20,000 modelled investor
              decisions set in real Indian market conditions from 2008 to today. Then both choices are played out over a
              thousand possible futures of {horizonPhrase(horizon)}, built from how Indian shares and gold really moved,
              with tax and charges included.
            </p>
          ) : (
            <p>
              Your situation is compared with patterns seen across thousands of investors, then both choices are played
              out over a thousand possible 20-year futures. The pattern read looks at your situation; the recommendation
              weighs the action you chose.
            </p>
          )}
        </div>
      </div>
    </details>
  );
}

function ResultView({ d }: { d: Decision }) {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`Analysis · ${formatDate(d.submitted_at, true)}`}
        title={
          <>
            {decisionTitle(d)} <span className="text-muted-foreground">· {INTENT_LABEL[d.decision_intent]}</span>
          </>
        }
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span className="tabular">
              {d.holding_quantity.toLocaleString("en-IN", { maximumFractionDigits: 3 })} units · {formatPrice(d.avg_buy_price)} → {formatPrice(d.current_price)}
            </span>
            <span className={cn("tabular font-medium", d.unrealized_pnl_pct >= 0 ? "text-success" : "text-danger")}>{formatPct(d.unrealized_pnl_pct)}</span>
            <BiasBadge bias={d.bias_detected} confidence={d.bias_confidence} size="md" />
          </span>
        }
        actions={
          <Button asChild variant="outline">
            <Link to="/app/new">
              <PlusCircle /> New analysis
            </Link>
          </Button>
        }
      />

      <VerdictHero d={d} />

      <BothSidesCard d={d} />
      <PortfolioCard d={d} />

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <SimulationCard d={d} />
        <BiasCard d={d} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <ExplanationCard d={d} />
        <SignalsCard d={d} />
      </div>

      <CausalCard d={d} />

      {d.user_reasoning && <OwnWordsCard d={d} />}

      <SecureRecordCard d={d} />

      <Methodology d={d} />

      <p className="pb-4 text-center text-xs text-subtle-foreground">For information and education. Not investment advice.</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function DecisionPage() {
  const { id } = useParams();
  const { data: d, isPending, isError } = useDecision(id);

  if (isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-1/2" />
        <Skeleton className="h-56 rounded-[2rem]" />
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <Skeleton className="h-96 rounded-3xl" />
          <Skeleton className="h-96 rounded-3xl" />
        </div>
      </div>
    );
  }

  if (isError || !d) {
    return (
      <div className="mx-auto max-w-md py-16 text-center">
        <h1 className="text-3xl">Analysis not found</h1>
        <p className="mt-3 text-muted-foreground">It may belong to another account, or the link is wrong.</p>
        <Button asChild className="mt-8">
          <Link to="/app/history">
            <ArrowLeft /> Back to history
          </Link>
        </Button>
      </div>
    );
  }

  if (d.status === "pending" || d.status === "processing") return <LiveView decision={d} />;

  if (d.status === "failed") {
    return (
      <div className="mx-auto max-w-lg py-12">
        <Card>
          <CardContent className="p-8 text-center">
            <span className="mx-auto flex size-14 items-center justify-center rounded-3xl bg-danger-mist text-danger">
              <CircleAlert className="size-7" />
            </span>
            <h1 className="mt-5 text-2xl">This analysis couldn't finish</h1>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">Something went wrong on our side. Please try again.</p>
            <Button asChild className="mt-7">
              <Link to="/app/new">Try again</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <ResultView d={d} />;
}
