import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, PlusCircle, Search } from "lucide-react";
import { PageHeader } from "@/components/layouts";
import { BiasBadge, VerdictBadge } from "@/components/decision";
import { Button } from "@/components/ui/button";
import { Card, Input, Skeleton } from "@/components/ui/primitives";
import { BIAS_META, BIAS_ORDER, INTENT_LABEL, decisionTitle } from "@/lib/domain";
import { useDecisions } from "@/lib/queries";
import type { BiasType } from "@/lib/types";
import { cn, formatDate, formatINR, formatPct } from "@/lib/utils";

const PAGE = 10;

export default function HistoryPage() {
  const navigate = useNavigate();
  // History is small per user; fetch the newest 100 and filter in the browser.
  const { data, isPending } = useDecisions(100, 0);
  const [bias, setBias] = React.useState<BiasType | "all">("all");
  const [query, setQuery] = React.useState("");
  const [page, setPage] = React.useState(0);

  const filtered = React.useMemo(() => {
    const q = query.trim().toUpperCase();
    return (data?.items ?? []).filter(
      (d) => (bias === "all" || d.bias_detected === bias) && (!q || decisionTitle(d).toUpperCase().includes(q)),
    );
  }, [data, bias, query]);

  React.useEffect(() => setPage(0), [bias, query]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const rows = filtered.slice(page * PAGE, page * PAGE + PAGE);

  return (
    <>
      <PageHeader
        eyebrow="History"
        title="Every decision you've run past Folium"
        description="Open any analysis to see its full reasoning and projection."
        actions={
          <Button asChild>
            <Link to="/app/new">
              <PlusCircle /> New analysis
            </Link>
          </Button>
        }
      />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by bias">
          {(["all", ...BIAS_ORDER] as const).map((b) => (
            <button
              key={b}
              onClick={() => setBias(b)}
              aria-pressed={bias === b}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm transition-colors",
                bias === b ? "border-teal bg-teal-mist text-teal-ink" : "border-border bg-surface text-muted-foreground hover:text-foreground",
              )}
            >
              {b !== "all" && <span className={cn("size-2 rounded-full", BIAS_META[b].dot)} />}
              {b === "all" ? "All" : BIAS_META[b].short}
            </button>
          ))}
        </div>
        <div className="relative sm:w-64">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-subtle-foreground" />
          <Input aria-label="Search by holding" placeholder="Search holding" className="pl-10" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </div>

      <Card className="overflow-hidden">
        {isPending ? (
          <div className="space-y-3 p-6">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <p className="font-serif text-xl">{data?.items.length ? "Nothing matches that filter" : "No analyses yet"}</p>
            <p className="mt-2 text-sm text-muted-foreground">
              {data?.items.length ? "Try another bias or clear the search." : "Your analyses will appear here."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-subtle-foreground">
                  <th className="px-6 py-3.5 font-medium">Stock</th>
                  <th className="px-3 py-3.5 font-medium">Your instinct</th>
                  <th className="px-3 py-3.5 text-right font-medium">P&amp;L</th>
                  <th className="px-3 py-3.5 font-medium">Bias</th>
                  <th className="px-3 py-3.5 font-medium">Our read</th>
                  <th className="px-3 py-3.5 text-right font-medium">Difference by your horizon</th>
                  <th className="px-6 py-3.5 text-right font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((d) => (
                  <tr
                    key={d.decision_id}
                    onClick={() => navigate(`/app/decisions/${d.decision_id}`)}
                    className="cursor-pointer transition-colors hover:bg-surface-2/60"
                  >
                    <td className="px-6 py-4">
                      <Link to={`/app/decisions/${d.decision_id}`} className="font-medium hover:text-primary" onClick={(e) => e.stopPropagation()}>
                        {decisionTitle(d)}
                      </Link>
                      <p className="tabular text-xs text-subtle-foreground">
                        {d.holding_quantity.toLocaleString("en-IN", { maximumFractionDigits: 3 })} {d.portfolio_context?.asset_type === "mf" ? "units" : "shares"}
                      </p>
                    </td>
                    <td className="px-3 py-4">{INTENT_LABEL[d.decision_intent]}</td>
                    <td className={cn("tabular px-3 py-4 text-right", d.unrealized_pnl_pct >= 0 ? "text-success" : "text-danger")}>
                      {formatPct(d.unrealized_pnl_pct)}
                    </td>
                    <td className="px-3 py-4">
                      {d.status === "complete" ? (
                        <BiasBadge bias={d.bias_detected} confidence={d.bias_confidence} />
                      ) : (
                        <span className="text-xs capitalize text-muted-foreground">{d.status}</span>
                      )}
                    </td>
                    <td className="px-3 py-4">
                      <VerdictBadge verdict={d.recommendation} />
                    </td>
                    <td className="tabular px-3 py-4 text-right">{formatINR(d.opportunity_cost_inr)}</td>
                    <td className="px-6 py-4 text-right text-muted-foreground">{formatDate(d.submitted_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {pages > 1 && (
        <div className="mt-5 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {filtered.length} analyses · page {page + 1} of {pages}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="icon" aria-label="Previous page" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft />
            </Button>
            <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight />
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
