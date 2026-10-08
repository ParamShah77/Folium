import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Check, CircleAlert, Loader2 } from "lucide-react";
import { BIAS_META, PIPELINE_STEPS, VERDICT_META, confidenceLevel } from "@/lib/domain";
import type { BiasType, PipelineEvent, SimulationCurves, Verdict } from "@/lib/types";
import { cn, formatINR } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Badges                                                              */
/* ------------------------------------------------------------------ */

export function BiasBadge({
  bias,
  confidence,
  className,
  size = "sm",
}: {
  bias: BiasType | null;
  confidence?: number | null;
  className?: string;
  size?: "sm" | "md";
}) {
  if (!bias) return <span className="text-sm text-subtle-foreground">—</span>;
  const meta = BIAS_META[bias];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium",
        size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm",
        meta.soft,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", meta.dot)} />
      {meta.label}
      {confidence !== null && confidence !== undefined && size === "md" && (
        <span className="opacity-75">· {confidenceLevel(confidence).label.replace(" confidence", "")}</span>
      )}
    </span>
  );
}

export function VerdictBadge({ verdict, className }: { verdict: Verdict | null; className?: string }) {
  if (!verdict) return <span className="text-sm text-subtle-foreground">—</span>;
  const meta = VERDICT_META[verdict];
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", meta.soft, className)}>
      {meta.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Wealth fan chart over the investor's horizon                        */
/* ------------------------------------------------------------------ */

interface ChartRow {
  year: number;
  holdBand: [number, number];
  sellBand: [number, number];
  hold: number;
  sell: number;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartRow }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-2xl border border-border bg-surface px-4 py-3 text-sm shadow-lift">
      <p className="mb-2 font-medium">{row.year === 0 ? "Today" : `Year ${row.year}`}</p>
      <p className="flex items-center justify-between gap-6">
        <span className="flex items-center gap-2 text-muted-foreground">
          <span className="size-2 rounded-full bg-hold" /> Hold
        </span>
        <span className="tabular font-medium">{formatINR(row.hold)}</span>
      </p>
      <p className="mt-1 flex items-center justify-between gap-6">
        <span className="flex items-center gap-2 text-muted-foreground">
          <span className="size-2 rounded-full bg-sell" /> Sell
        </span>
        <span className="tabular font-medium">{formatINR(row.sell)}</span>
      </p>
      <p className="mt-2 text-xs text-subtle-foreground">Most likely, with the range from a bad to a good outcome</p>
    </div>
  );
}

/** Short axis labels: ₹26 L, ₹6.5 L, ₹1.2 Cr, ₹85k. The tooltip keeps full figures. */
function axisINR(v: number): string {
  const a = Math.abs(v);
  const short = (x: number) => String(Number(x.toFixed(1)));
  if (a >= 1e7) return `₹${short(v / 1e7)} Cr`;
  if (a >= 1e5) return `₹${short(v / 1e5)} L`;
  if (a >= 1e3) return `₹${Math.round(v / 1e3)}k`;
  return `₹${Math.round(v)}`;
}

export function WealthFanChart({ curves, height = 300 }: { curves: SimulationCurves; height?: number }) {
  const data: ChartRow[] = curves.years.map((year, i) => ({
    year,
    holdBand: [curves.hold_p10[i], curves.hold_p90[i]],
    sellBand: [curves.sell_p10[i], curves.sell_p90[i]],
    hold: curves.hold_p50[i],
    sell: curves.sell_p50[i],
  }));

  return (
    <div
      style={{ height }}
      role="img"
      aria-label={`Projected wealth over ${curves.horizon_years ?? 20} years for holding versus selling`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="year"
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--subtle-foreground)", fontSize: 12 }}
            tickFormatter={(y: number) => (y === 0 ? "Now" : `${y}y`)}
            interval={4}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={64}
            tick={{ fill: "var(--subtle-foreground)", fontSize: 12 }}
            tickFormatter={axisINR}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--border-strong)", strokeDasharray: "3 4" }} />
          <Area type="monotone" dataKey="sellBand" stroke="none" fill="var(--sell)" fillOpacity={0.16} isAnimationActive={false} />
          <Area type="monotone" dataKey="holdBand" stroke="none" fill="var(--hold)" fillOpacity={0.18} isAnimationActive={false} />
          <Line type="monotone" dataKey="sell" stroke="var(--sell)" strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="hold" stroke="var(--hold)" strokeWidth={2.75} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Live pipeline                                                       */
/* ------------------------------------------------------------------ */

type StepState = "waiting" | "running" | "done" | "error";

export interface StreamState {
  steps: Record<string, StepState>;
  events: Record<string, PipelineEvent>;
  terminal: "complete" | "failed" | "timeout" | null;
  error?: string;
  connection: "connecting" | "open" | "fallback";
}

const initialSteps = () =>
  Object.fromEntries(PIPELINE_STEPS.map((s) => [s.key, "waiting" as StepState])) as Record<string, StepState>;

/**
 * Subscribes to GET /v1/decisions/{id}/stream. The server replays every event
 * already published, so opening the page mid-analysis (or reloading) shows the
 * full history. If the stream can't be opened, the caller falls back to polling.
 */
export function useDecisionStream(id: string | undefined, enabled: boolean): StreamState {
  const qc = useQueryClient();
  const [state, setState] = React.useState<StreamState>({
    steps: initialSteps(),
    events: {},
    terminal: null,
    connection: "connecting",
  });

  React.useEffect(() => {
    if (!id || !enabled) return;
    const es = new EventSource(`/v1/decisions/${id}/stream`, { withCredentials: true });
    let finished = false;

    es.onopen = () => setState((s) => ({ ...s, connection: "open" }));
    es.onmessage = (msg) => {
      let ev: PipelineEvent;
      try {
        ev = JSON.parse(msg.data);
      } catch {
        return;
      }
      if (ev.step === "complete" || ev.step === "failed" || ev.step === "timeout") {
        finished = true;
        es.close();
        setState((s) => ({
          ...s,
          terminal: ev.step as StreamState["terminal"],
          error: typeof ev.error === "string" ? ev.error : undefined,
        }));
        qc.invalidateQueries({ queryKey: ["decision", id] });
        qc.invalidateQueries({ queryKey: ["decisions"] });
        qc.invalidateQueries({ queryKey: ["stats"] });
        return;
      }
      setState((s) => ({
        ...s,
        steps: { ...s.steps, [ev.step]: ev.status === "done" ? "done" : ev.status === "error" ? "error" : "running" },
        events: { ...s.events, [ev.step]: ev },
      }));
    };
    es.onerror = () => {
      if (finished) return;
      // EventSource retries on its own; if it never opened, poll instead.
      setState((s) => (s.connection === "open" ? s : { ...s, connection: "fallback" }));
      if (es.readyState === EventSource.CLOSED) setState((s) => ({ ...s, connection: "fallback" }));
    };
    return () => es.close();
  }, [id, enabled, qc]);

  return state;
}

function stepSummary(key: string, ev: PipelineEvent | undefined): string | null {
  if (!ev || ev.status !== "done") return null;
  switch (key) {
    case "bias_detection":
      return typeof ev.bias === "string"
        ? `${BIAS_META[ev.bias as BiasType]?.label ?? ev.bias} · ${confidenceLevel(Number(ev.confidence)).label.toLowerCase()}`
        : null;
    case "simulation":
      return ev.prob_hold_better !== undefined
        ? `Holding came out ahead in ${Math.round(Number(ev.prob_hold_better) * 100)}% of possible futures`
        : null;
    case "explanation":
      return typeof ev.headline === "string" ? ev.headline : null;
    case "debate":
      return typeof ev.verdict === "string" ? `Leaning ${VERDICT_META[ev.verdict as Verdict]?.label.toLowerCase()}` : null;
    case "audit":
      return "Saved";
    default:
      return null;
  }
}

export function PipelineTimeline({ stream }: { stream: StreamState }) {
  return (
    <ol className="space-y-1">
      {PIPELINE_STEPS.map((step, i) => {
        const st = stream.steps[step.key];
        const summary = stepSummary(step.key, stream.events[step.key]);
        return (
          <li key={step.key} className="relative flex gap-4 pb-6 last:pb-0">
            {i < PIPELINE_STEPS.length - 1 && (
              <span
                className={cn(
                  "absolute left-[15px] top-9 h-[calc(100%-2.25rem)] w-px transition-colors duration-500",
                  st === "done" ? "bg-teal" : "bg-border",
                )}
                aria-hidden
              />
            )}
            <span
              className={cn(
                "relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border transition-all duration-500",
                st === "done" && "border-teal bg-teal text-primary-foreground dark:text-[#102624]",
                st === "running" && "border-teal bg-teal-mist text-primary",
                st === "waiting" && "border-border bg-surface text-subtle-foreground",
                st === "error" && "border-danger bg-danger-mist text-danger",
              )}
            >
              {st === "done" ? (
                <Check className="size-4" />
              ) : st === "running" ? (
                <Loader2 className="size-4 animate-spin" />
              ) : st === "error" ? (
                <CircleAlert className="size-4" />
              ) : (
                <span className="text-xs font-medium">{i + 1}</span>
              )}
            </span>
            <div className="min-w-0 pt-1">
              <p className={cn("font-medium", st === "waiting" && "text-muted-foreground")}>{step.label}</p>
              {summary && <p className="mt-1.5 animate-fade-up text-sm text-teal-ink">{summary}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
