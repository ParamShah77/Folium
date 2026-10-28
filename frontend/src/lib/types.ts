export type BiasType = "loss_aversion" | "herd_behavior" | "disposition_effect" | "rational";
export type Intent = "sell" | "hold" | "buy_more";
export type Verdict = "HOLD" | "SELL" | "BUY_MORE";
export type DecisionStatus = "pending" | "processing" | "complete" | "failed";
export type Strategy = "conservative" | "moderate" | "aggressive";

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  mfa_enabled: boolean;
  /** False for an account made with Google until a password is set. */
  has_password?: boolean;
  /** Tier 1 (age, income, risk, horizon) still to fill in. */
  needs_profile?: boolean;
}

export interface Profile {
  user_id: string;
  email: string;
  email_verified: boolean;
  name: string;
  role: string;
  mfa_enabled: boolean;
  oauth_provider: string | null;
  phone: string | null;
  age: number | null;
  monthly_income: number | null;
  monthly_expense: number | null;
  risk_tolerance: number | null;
  investment_horizon: number | null;
  has_emergency_fund: boolean | null;
  financial_strategy: Strategy | null;
  goal: string | null;
  monthly_emi: number | null;
  rent_paid: number | null;
  education_monthly: number | null;
  education_end_year: number | null;
  created_at: string;
  last_login_at: string | null;
  ai_consent?: boolean;
}

export interface ShapFactor {
  feature: string;
  label: string;
  value: number;
  shap_impact: number;
  /** Share of the total pull, 0..1 (bias model v4 only). */
  share?: number | null;
  /** v4: pushed toward / against the pattern found. v3's sign was unreliable, so it is not shown. */
  direction: "toward" | "against" | "increases_bias" | "decreases_bias" | null;
}

export interface CausalEffect {
  treatment: string;
  label: string;
  effect: number;
  method: string | null;
  refutation_passed: boolean;
  refutations: { test: string; p_value: number | null }[];
  /* causal v4: per situation and action */
  unit?: string;
  action?: Intent;
  action_words?: string;
  situation?: string;
  share_taking_action?: number;
}

export interface Intervention {
  key: string;
  description: string;
  original_sell_prob: number;
  new_sell_prob: number;
  delta_sell_prob: number;
  recommendation: string | null;
  /* causal v4: the probabilities are of this action, not always selling */
  action?: Intent;
  assumption?: string | null;
}

export interface GapExplanation {
  lang: "en" | "hi";
  lang_name: string;
  headline: string;
  recommendation: string;
  sections: { key: string; title: string; text: string }[];
  polished: boolean;
}

export interface ExplainerOutput {
  own_words?: OwnWords | null;
  headline?: string;
  explanation?: { en: GapExplanation; hi: GapExplanation } | null;
  story?: { title: string; body: string }[] | null;
  factors?: ShapFactor[];
  bias?: {
    model: string;
    bias_type: BiasType;
    confidence: number;
    probabilities?: Record<string, number>;
    model_probabilities?: Record<string, number>;
    allowed?: string[];
    assumed_defaults?: string[];
    market_context?: "captured" | "unavailable";
    fixed_inputs?: string[];
    portfolio_aware?: boolean;
    model_inputs?: Record<string, number | string>;
  };
  causal?: {
    primary: CausalEffect | null;
    context: CausalEffect[];
    intervention: Intervention | null;
    source: string;
  };
}

export interface SimulationCurves {
  engine: string;
  horizon_years: number;
  n_paths: number;
  years: number[];
  hold_p10: number[];
  hold_p50: number[];
  hold_p90: number[];
  sell_p10: number[];
  sell_p50: number[];
  sell_p90: number[];
  invested: number;
  allocation_basis?: "portfolio" | "risk_profile";
  hold_start: number;
  sell_start: number;
  hold_stock_allocation: number;
  sell_stock_allocation: number;
  hold_mean: number;
  sell_mean: number;
  prob_hold_better: number;
  wealth_gap_pct: number;
  assumed_defaults?: string[];
  /* simulation v2 */
  horizon_source?: "profile" | "default";
  values_basis?: string;
  fixed_inputs?: string[];
  sale?: {
    value: number;
    gain: number;
    tax_kind: "short_term" | "long_term";
    tax: number;
    costs: number;
    proceeds: number;
    destination: Record<"gold" | "fixed_deposits" | "savings", number>;
  };
  portfolio?: {
    liquid_today: number;
    hold_median_end: number;
    sell_median_end: number;
    decision_share_of_end_wealth: number;
    monthly_sip: number;
  };
  growth?: { shares: number; gold: number; fixed_deposits: number; savings: number; slab_rate_on_interest: number };
  holding_risk?: { asset_type: "equity" | "mf"; beta: number; specific_vol: number; source: "measured" | "typical" };
}

export interface DebateCase {
  side: "stay" | "leave";
  title: string;
  points: string[];
  text: string;
  worded_by: "numbers" | "gemini";
}

export interface DebateTranscript {
  engine: string;
  llm_debate: boolean;
  verdict: Verdict;
  reasons: string[];
  /* Phase B3: the case for each side; never part of the verdict */
  cases?: DebateCase[];
}

/** Phase B3: "Why? In your own words", read and compared with the reading. */
export interface OwnWords {
  agreement: "agrees" | "differs" | "none";
  note: string | null;
  cues: { kind: string; suggests: BiasType; quote: string; label: string }[];
  facts: { kind: "cash_need" | "rebalance" | "goal_near"; quote: string }[];
  cash_need: boolean;
  cash_need_quote: string | null;
  source: "rules" | "rules+gemini" | null;
}

export interface Decision {
  decision_id: string;
  status: DecisionStatus;
  pipeline_step: string | null;
  error_message: string | null;
  symbol: string;
  exchange: string;
  holding_quantity: number;
  avg_buy_price: number;
  current_price: number;
  unrealized_pnl_pct: number;
  decision_intent: Intent;
  user_reasoning: string | null;
  holding_period_days: number | null;
  market_trend: "bull" | "bear" | "sideways" | null;
  sector: string | null;
  nifty_1m_return: number | null;
  nifty_volatility_30d: number | null;
  nifty_1d_change: number | null;
  vix_value: number | null;
  market_data_source: "live" | "cache" | "unavailable" | null;
  bias_detected: BiasType | null;
  bias_confidence: number | null;
  recommendation: Verdict | null;
  causal_effect: number | null;
  opportunity_cost_inr: number | null;
  hold_median_20y: number | null;
  hold_p10_20y: number | null;
  hold_p90_20y: number | null;
  sell_median_20y: number | null;
  sell_p10_20y: number | null;
  sell_p90_20y: number | null;
  explainer_output: ExplainerOutput | null;
  debate_transcript: DebateTranscript | null;
  simulation_curves: SimulationCurves | null;
  tax_category: "STCG" | "LTCG" | null;
  holding_id: string | null;
  portfolio_context: PortfolioContext | null;
  submitted_at: string;
  completed_at: string | null;
}

export type DecisionSummary = Pick<
  Decision,
  | "decision_id"
  | "symbol"
  | "exchange"
  | "status"
  | "pipeline_step"
  | "decision_intent"
  | "holding_quantity"
  | "avg_buy_price"
  | "current_price"
  | "unrealized_pnl_pct"
  | "bias_detected"
  | "bias_confidence"
  | "recommendation"
  | "opportunity_cost_inr"
  | "hold_median_20y"
  | "sell_median_20y"
  | "error_message"
  | "holding_id"
  | "portfolio_context"
  | "submitted_at"
  | "completed_at"
>;

export interface DecisionStats {
  total: number;
  completed: number;
  by_bias: Record<BiasType, number>;
  dominant_bias: BiasType | null;
  rational_share: number | null;
  avg_confidence: number | null;
  wealth_at_stake_inr: number;
}

export interface MarketIndex {
  key: string;
  label: string;
  price: number;
  change_pct: number | null;
  direction: "up" | "down" | "neutral";
}

export interface MarketRibbon {
  data_source: string;
  last_updated?: string;
  indices: MarketIndex[];
}

export interface AppConfig {
  google_oauth: boolean;
  dev_mailbox: boolean;
  ai_help?: boolean;
  environment: string;
}

export interface PipelineEvent {
  step: string;
  status: "running" | "done" | "error";
  seq: number;
  decision_id: string;
  error?: string;
  [key: string]: unknown;
}

export interface PortfolioContext {
  holding_id: string;
  asset_type: "equity" | "mf";
  name?: string;
  position_value: number;
  position_share: number | null;
  liquid: number;
  net_worth: number;
  equity_share: number;
  gold_share?: number;
  real_estate?: number;
  liabilities?: number;
  monthly_income: number | null;
  rent_received: number;
  committed_outflow: number | null;
  monthly_surplus: number | null;
  holdings_count: number;
}

export interface Holding {
  holding_id: string;
  asset_type: "equity" | "mf";
  symbol: string;
  exchange: "NSE" | "BSE";
  name: string;
  scheme_code: string | null;
  quantity: number;
  avg_buy_price: number;
  buy_date: string | null;
  current_price: number | null;
  price_source: "live" | "unavailable";
  price_as_of: string | null;
  day_change_pct: number | null;
  invested: number;
  value: number;
  pnl: number | null;
  pnl_pct: number | null;
}

export interface OtherAssets {
  gold_grams: number | null;
  gold_buy_price_per_gram: number | null;
  real_estate_value: number | null;
  home_loan_outstanding: number | null;
  other_loans_outstanding: number | null;
  rent_received: number | null;
  fixed_deposits: number | null;
  savings_balance: number | null;
  monthly_sip: number | null;
}

export interface PortfolioSummary {
  liquid: number;
  net_worth: number;
  invested_in_holdings: number;
  holdings_value: number;
  allocation: Record<"stocks" | "mutual_funds" | "gold" | "fixed_deposits" | "savings", { value: number; share: number }>;
  equity_share: number;
  real_estate: number;
  liabilities: number;
  monthly_income: number | null;
  rent_received: number;
  committed_outflow: number | null;
  monthly_surplus: number | null;
  gold: { grams: number; price_per_gram: number | null; price_source: "live" | "buy_price" | "none"; basis: string | null };
}

export interface Portfolio {
  holdings: Holding[];
  assets: OtherAssets;
  summary: PortfolioSummary;
}

/** GET /v1/decisions/{id}/verify — the tamper-evident record (Phase B1). */
export interface VerifyResult {
  verified: boolean;
  record: {
    status: "verified" | "changed" | "missing" | "matches_earlier_format";
    fingerprint?: string;
    recorded_at?: string;
    times_recorded?: number;
    parts?: { inputs?: "unchanged" | "changed"; analysis?: "unchanged" | "changed" };
    changed?: string[];
    detail?: string;
  };
  chain: {
    valid: boolean;
    entries: number;
    linked: number;
    anchor: "current" | "earlier format" | null;
    problems: { kind: string; log_id: string | null; detail: string }[];
  };
}
