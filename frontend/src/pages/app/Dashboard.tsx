import { Link } from "react-router-dom";
import { ArrowRight, ArrowUpRight, Leaf, PlusCircle, Sparkles, UserRound } from "lucide-react";
import { PageHeader } from "@/components/layouts";
import { BiasBadge, VerdictBadge } from "@/components/decision";
import { Button } from "@/components/ui/button";
import { Alert, Card, CardContent, CardDescription, CardHeader, CardTitle, Skeleton } from "@/components/ui/primitives";
import { BIAS_META, BIAS_ORDER, INTENT_LABEL, decisionTitle, isProfileComplete } from "@/lib/domain";
import { useDecisions, usePortfolio, useProfile, useStats } from "@/lib/queries";
import type { DecisionStats, PortfolioSummary } from "@/lib/types";
import { cn, formatINR, formatPct, relativeTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth";

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function StatCard({ label, value, hint, tone = "plain" }: { label: string; value: React.ReactNode; hint?: string; tone?: "plain" | "teal" | "blush" }) {
  return (
    <div
      className={cn(
        "rounded-3xl p-5",
        tone === "plain" && "border border-border bg-surface shadow-soft",
        tone === "teal" && "bg-teal-mist",
        tone === "blush" && "bg-blush",
      )}
    >
      <p className={cn("text-[13px]", tone === "blush" ? "text-rose" : tone === "teal" ? "text-teal-ink" : "text-muted-foreground")}>
        {label}
      </p>
      <p className="tabular mt-2 font-serif text-[1.75rem] leading-none">{value}</p>
      {hint && <p className="mt-2 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function BiasMix({ stats }: { stats: DecisionStats }) {
  const total = stats.completed || 1;
  return (
    <div className="space-y-4">
      <div className="flex h-3 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        {BIAS_ORDER.map((b) => (
          <span
            key={b}
            className={cn("h-full transition-all duration-700", BIAS_META[b].dot)}
            style={{ width: `${(stats.by_bias[b] / total) * 100}%` }}
          />
        ))}
      </div>
      <ul className="grid grid-cols-2 gap-3">
        {BIAS_ORDER.map((b) => (
          <li key={b} className="flex items-center justify-between gap-2 rounded-2xl bg-surface-2/70 px-3.5 py-2.5">
            <span className="flex items-center gap-2 text-sm">
              <span className={cn("size-2 rounded-full", BIAS_META[b].dot)} />
              {BIAS_META[b].label}
            </span>
            <span className="tabular text-sm font-medium">{stats.by_bias[b]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PortfolioSnapshot({ s, holdings }: { s: PortfolioSummary; holdings: number }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>Your portfolio</CardTitle>
          <CardDescription>{holdings} holdings, live-priced</CardDescription>
        </div>
        <Button asChild variant="ghost" size="sm">
          <Link to="/app/portfolio">
            Open <ArrowRight />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-3 gap-3">
          {[
            ["Net worth", formatINR(s.net_worth)],
            ["Liquid", formatINR(s.liquid)],
            ["Surplus / month", s.monthly_surplus == null ? "—" : formatINR(s.monthly_surplus)],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl bg-surface-2/70 px-3 py-3">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="tabular mt-1 font-serif text-lg leading-tight">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

function EmptyState({ hasPortfolio }: { hasPortfolio: boolean }) {
  return (
    <Card className="overflow-hidden">
      <div className="grid items-center gap-8 p-8 sm:p-10 md:grid-cols-[1.2fr_1fr]">
        <div>
          <span className="flex size-12 items-center justify-center rounded-2xl bg-teal-mist text-primary">
            <Leaf className="size-6" />
          </span>
          <h2 className="mt-5 text-3xl leading-tight">
            {hasPortfolio ? "Start with a decision you're weighing" : "Start by adding what you own"}
          </h2>
          <p className="mt-3 max-w-md leading-relaxed text-muted-foreground">
            {hasPortfolio
              ? "Pick a holding and tell Folium what you're tempted to do. In under a minute you'll see the bias behind it and what it means by the time you need the money."
              : "Add your shares and funds, and optionally gold, deposits, property and loans. Every analysis is then judged against your whole picture."}
          </p>
          <Button asChild size="lg" className="mt-7">
            <Link to={hasPortfolio ? "/app/new" : "/app/portfolio"}>
              {hasPortfolio ? "Analyse your first decision" : "Set up your portfolio"} <ArrowRight />
            </Link>
          </Button>
        </div>
        <ol className="space-y-3">
          {["Add your portfolio", "Pick a holding and your instinct", "See the bias and both futures"].map((t, i) => (
            <li key={t} className="flex items-center gap-3 rounded-2xl bg-surface-2/70 px-4 py-3.5">
              <span className="flex size-7 items-center justify-center rounded-full bg-surface text-xs font-medium text-primary shadow-soft">
                {i + 1}
              </span>
              <span className="text-sm">{t}</span>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const stats = useStats();
  const recent = useDecisions(6, 0);
  const profile = useProfile();
  const portfolio = usePortfolio();
  const holdingsCount = portfolio.data?.holdings.length ?? 0;
  const first = user?.name.split(" ")[0];

  const incomplete = profile.data && !isProfileComplete(profile.data);
  const hasDecisions = (stats.data?.total ?? 0) > 0;

  return (
    <>
      <PageHeader
        eyebrow={new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
        title={
          <>
            {greeting()}, <span className="italic text-primary">{first}</span>
          </>
        }
        description="Here's how your recent investing decisions are shaping up."
        actions={
          <Button asChild>
            <Link to="/app/new">
              <PlusCircle /> New analysis
            </Link>
          </Button>
        }
      />

      {incomplete && (
        <Alert tone="warning" icon={<UserRound />} className="mb-6" title="Your investor profile has gaps">
          Analyses still run, but missing details are filled with typical values.{" "}
          <Link to="/app/settings" className="font-medium underline underline-offset-2">
            Complete your profile
          </Link>
        </Alert>
      )}

      {stats.isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 rounded-3xl" />
          ))}
        </div>
      ) : !hasDecisions ? (
        <div className="space-y-6">
          <EmptyState hasPortfolio={holdingsCount > 0} />
          {portfolio.data && holdingsCount > 0 && <PortfolioSnapshot s={portfolio.data.summary} holdings={holdingsCount} />}
        </div>
      ) : (
        stats.data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Decisions analysed" value={stats.data.completed} hint={`${stats.data.total} submitted in total`} />
              <StatCard
                label="Most frequent bias"
                tone="blush"
                value={stats.data.dominant_bias ? BIAS_META[stats.data.dominant_bias].short : "None"}
                hint={stats.data.dominant_bias ? "Worth watching for" : "Every call looked rational"}
              />
              <StatCard
                label="Rational decisions"
                value={stats.data.rational_share !== null ? formatPct(stats.data.rational_share, 0, false) : "—"}
                hint="Share with no strong bias"
              />
              <StatCard
                label="Wealth at stake"
                tone="teal"
                value={formatINR(stats.data.wealth_at_stake_inr)}
                hint="What your sell ideas could cost, after tax, by your horizon"
              />
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
              <Card>
                <CardHeader className="flex-row items-center justify-between">
                  <div>
                    <CardTitle>Recent decisions</CardTitle>
                    <CardDescription>Your latest analyses</CardDescription>
                  </div>
                  <Button asChild variant="ghost" size="sm">
                    <Link to="/app/history">
                      View all <ArrowRight />
                    </Link>
                  </Button>
                </CardHeader>
                <CardContent className="pt-4">
                  <ul className="divide-y divide-border">
                    {recent.data?.items.map((d) => (
                      <li key={d.decision_id}>
                        <Link
                          to={`/app/decisions/${d.decision_id}`}
                          className="group -mx-3 flex items-center gap-4 rounded-2xl px-3 py-3.5 transition-colors hover:bg-surface-2/70"
                        >
                          <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-surface-2 font-serif text-sm">
                            {decisionTitle(d).slice(0, 2).toUpperCase()}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-medium">
                              {decisionTitle(d)}{" "}
                              <span className="font-normal text-muted-foreground">· {INTENT_LABEL[d.decision_intent]}</span>
                            </p>
                            <p className="text-[13px] text-subtle-foreground">
                              <span className={cn("tabular", d.unrealized_pnl_pct >= 0 ? "text-success" : "text-danger")}>
                                {formatPct(d.unrealized_pnl_pct)}
                              </span>{" "}
                              · {relativeTime(d.submitted_at)}
                            </p>
                          </div>
                          <div className="hidden flex-col items-end gap-1.5 sm:flex">
                            {d.status === "complete" ? (
                              <>
                                <BiasBadge bias={d.bias_detected} />
                                <VerdictBadge verdict={d.recommendation} />
                              </>
                            ) : (
                              <span className="text-xs capitalize text-muted-foreground">{d.status}</span>
                            )}
                          </div>
                          <ArrowUpRight className="size-4 text-subtle-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>

              <div className="space-y-6">
                {portfolio.data && holdingsCount > 0 && <PortfolioSnapshot s={portfolio.data.summary} holdings={holdingsCount} />}
                <Card>
                  <CardHeader>
                    <CardTitle>Your bias pattern</CardTitle>
                    <CardDescription>Across {stats.data.completed} completed analyses</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <BiasMix stats={stats.data} />
                  </CardContent>
                </Card>
                <div className="rounded-3xl bg-blush p-6">
                  <Sparkles className="size-5 text-rose" />
                  <p className="mt-3 font-serif text-lg leading-snug text-rose">
                    {stats.data.dominant_bias
                      ? `When you feel the pull of ${BIAS_META[stats.data.dominant_bias].label.toLowerCase()}, wait a day before acting.`
                      : "Your recent calls look steady. Keep checking before you act."}
                  </p>
                </div>
              </div>
            </div>
          </>
        )
      )}
    </>
  );
}
