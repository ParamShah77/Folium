import type { BiasType, Intent, Verdict } from "./types";

/** One fixed colour and voice per bias, used everywhere in the app. */
export const BIAS_META: Record<
  BiasType,
  { label: string; short: string; dot: string; text: string; soft: string; description: string }
> = {
  loss_aversion: {
    label: "Loss aversion",
    short: "Loss aversion",
    dot: "bg-bias-loss",
    text: "text-orange-ink",
    soft: "bg-orange-mist text-orange-ink",
    description: "Losses feel about twice as strong as gains, so pain can drive the decision.",
  },
  herd_behavior: {
    label: "Herd behaviour",
    short: "Herd",
    dot: "bg-bias-herd",
    text: "text-[#4d6a88] dark:text-bias-herd",
    soft: "bg-[#e9eff5] text-[#40607f] dark:bg-[#232c36] dark:text-bias-herd",
    description: "Following the crowd's fear or excitement instead of your own plan.",
  },
  disposition_effect: {
    label: "Disposition effect",
    short: "Disposition",
    dot: "bg-bias-disposition",
    text: "text-[#7d6224] dark:text-bias-disposition",
    soft: "bg-[#f6efdc] text-[#6f5620] dark:bg-[#352d1b] dark:text-bias-disposition",
    description: "Selling winners too early and holding on to losers too long.",
  },
  rational: {
    label: "Rational",
    short: "Rational",
    dot: "bg-bias-rational",
    text: "text-teal-ink",
    soft: "bg-teal-mist text-teal-ink",
    description: "No strong behavioural bias detected behind the decision.",
  },
};

export const BIAS_ORDER: BiasType[] = [
  "loss_aversion",
  "herd_behavior",
  "disposition_effect",
  "rational",
];

/** CSS variable per bias, for charts (recharts needs a colour string). */
export const BIAS_CHART_COLOR: Record<BiasType, string> = {
  loss_aversion: "var(--bias-loss)",
  herd_behavior: "var(--bias-herd)",
  disposition_effect: "var(--bias-disposition)",
  rational: "var(--bias-rational)",
};

export const INTENT_LABEL: Record<Intent, string> = {
  sell: "Sell",
  hold: "Hold",
  buy_more: "Buy more",
};

export const VERDICT_META: Record<Verdict, { label: string; soft: string }> = {
  HOLD: { label: "Hold", soft: "bg-teal-mist text-teal-ink" },
  SELL: { label: "Sell", soft: "bg-sell-mist text-foreground" },
  BUY_MORE: { label: "Buy more", soft: "bg-blush text-rose" },
};

/** The live-analysis steps, by plain title only. */
export const PIPELINE_STEPS: { key: string; label: string }[] = [
  { key: "bias_detection", label: "Reading your decision" },
  { key: "simulation", label: "Projecting both futures" },
  { key: "explanation", label: "Explaining what it means" },
  { key: "debate", label: "Forming a recommendation" },
  { key: "audit", label: "Saving a secure record" },
];

/** Confidence in words — same thresholds as the explanation engine's wording. */
export function confidenceLevel(c: number | null | undefined): { label: string; tone: "high" | "medium" | "low" } {
  const v = c ?? 0;
  if (v >= 0.85) return { label: "High confidence", tone: "high" };
  if (v >= 0.65) return { label: "Medium confidence", tone: "medium" };
  return { label: "Low confidence", tone: "low" };
}

/**
 * Five-question risk profile (FOLIUM_MASTER.md §4 Tier 1). Each answer
 * scores 0..3; the total maps to a 0..1 risk tolerance.
 */
export const RISK_QUIZ: { id: string; question: string; options: string[] }[] = [
  {
    id: "drop",
    question: "Your investments fall 20% in a month. What do you do?",
    options: ["Sell everything", "Sell some to be safe", "Wait it out", "Invest more while it's cheap"],
  },
  {
    id: "goal",
    question: "What matters most to you?",
    options: ["Never losing money", "Steady, modest growth", "Good growth with some swings", "Maximum growth"],
  },
  {
    id: "experience",
    question: "How long have you been investing in shares or funds?",
    options: ["Not yet", "Less than 2 years", "2 to 5 years", "More than 5 years"],
  },
  {
    id: "need",
    question: "When might you need most of this money?",
    options: ["Within a year", "In 1 to 3 years", "In 3 to 7 years", "Not for 7+ years"],
  },
  {
    id: "swing",
    question: "Which yearly outcome would you pick?",
    options: ["+4%, never a loss", "+8%, small dips possible", "+12%, a bad year could be -15%", "+16%, a bad year could be -30%"],
  },
];

export function riskFromQuiz(answers: Record<string, number>): number | null {
  const ids = RISK_QUIZ.map((q) => q.id);
  if (!ids.every((id) => answers[id] !== undefined)) return null;
  const total = ids.reduce((s, id) => s + answers[id], 0);
  return Math.round((total / (ids.length * 3)) * 100) / 100;
}

/** What to call a decision: the fund's name for mutual funds, else the ticker. */
export function decisionTitle(d: { symbol: string; portfolio_context?: { asset_type?: string; name?: string } | null }) {
  const c = d.portfolio_context;
  if (c?.asset_type === "mf" && c.name) return c.name.replace(/s*-s*(Direct|Regular)s+Plan.*$/i, "");
  return d.symbol;
}

export const GOALS = [
  "Wealth growth",
  "Retirement",
  "Child's education",
  "Buying a home",
  "Emergency fund",
];

export const STRATEGIES: { value: "conservative" | "moderate" | "aggressive"; label: string; hint: string }[] = [
  { value: "conservative", label: "Conservative", hint: "Protect what I have" },
  { value: "moderate", label: "Balanced", hint: "Steady growth, some ups and downs" },
  { value: "aggressive", label: "Growth", hint: "Maximise long-term growth" },
];

export function riskLabel(value: number | null | undefined) {
  if (value === null || value === undefined) return "Not set";
  if (value < 0.34) return "Cautious";
  if (value < 0.67) return "Moderate";
  return "Adventurous";
}

export function isProfileComplete(p: {
  age: number | null;
  risk_tolerance: number | null;
  investment_horizon: number | null;
  monthly_income: number | null;
}) {
  return p.age !== null && p.risk_tolerance !== null && p.investment_horizon !== null && p.monthly_income !== null;
}
