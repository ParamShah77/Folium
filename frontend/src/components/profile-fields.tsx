import { Check } from "lucide-react";
import { Field, Input, Slider, Switch } from "@/components/ui/primitives";
import { Select } from "@/components/ui/overlays";
import { GOALS, RISK_QUIZ, STRATEGIES, riskFromQuiz, riskLabel } from "@/lib/domain";
import type { Strategy } from "@/lib/types";
import { cn, formatINR } from "@/lib/utils";

/** Tier 1 of FOLIUM_MASTER.md §4 — what every analysis needs. */
export interface InvestorProfile {
  age: string;
  monthly_income: string;
  monthly_emi: string;
  rent_paid: string;
  education_monthly: string;
  education_end_year: string;
  has_emergency_fund: boolean;
  risk_tolerance: number;
  risk_answers: Record<string, number>;
  investment_horizon: number;
  financial_strategy: Strategy;
  goal: string;
}

export const EMPTY_PROFILE: InvestorProfile = {
  age: "",
  monthly_income: "",
  monthly_emi: "",
  rent_paid: "",
  education_monthly: "",
  education_end_year: "",
  has_emergency_fund: true,
  risk_tolerance: 0.5,
  risk_answers: {},
  investment_horizon: 15,
  financial_strategy: "moderate",
  goal: "Wealth growth",
};

export type ProfileErrors = Partial<Record<keyof InvestorProfile, string>>;

const money = (s: string) => (s.trim() === "" ? 0 : Number(s));
const THIS_YEAR = new Date().getFullYear();

export function validateProfile(v: InvestorProfile, opts: { requireQuiz?: boolean } = {}): ProfileErrors {
  const e: ProfileErrors = {};
  const age = Number(v.age);
  if (!v.age) e.age = "Enter your age";
  else if (!Number.isInteger(age) || age < 18 || age > 100) e.age = "Age must be between 18 and 100";
  if (v.monthly_income === "") e.monthly_income = "Enter your monthly income after tax";
  else if (!(Number(v.monthly_income) >= 0)) e.monthly_income = "Enter an amount of 0 or more";
  for (const k of ["monthly_emi", "rent_paid", "education_monthly"] as const) {
    if (v[k] !== "" && !(Number(v[k]) >= 0)) e[k] = "Enter an amount of 0 or more";
  }
  if (money(v.education_monthly) > 0 && v.education_end_year !== "") {
    const y = Number(v.education_end_year);
    if (!Number.isInteger(y) || y < THIS_YEAR || y > THIS_YEAR + 40) e.education_end_year = `Enter a year from ${THIS_YEAR}`;
  }
  if (opts.requireQuiz && riskFromQuiz(v.risk_answers) === null) e.risk_answers = "Answer all five questions";
  return e;
}

export function profilePayload(v: InvestorProfile) {
  const quiz = riskFromQuiz(v.risk_answers);
  return {
    age: Number(v.age),
    monthly_income: Number(v.monthly_income),
    monthly_emi: money(v.monthly_emi),
    rent_paid: money(v.rent_paid),
    education_monthly: money(v.education_monthly),
    education_end_year:
      money(v.education_monthly) > 0 && v.education_end_year !== "" ? Number(v.education_end_year) : null,
    has_emergency_fund: v.has_emergency_fund,
    risk_tolerance: quiz ?? Math.round(v.risk_tolerance * 1000) / 1000,
    investment_horizon: v.investment_horizon,
    financial_strategy: v.financial_strategy,
    goal: v.goal,
  };
}

export function RupeeInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">₹</span>
      <Input inputMode="decimal" className="pl-8" {...props} />
    </div>
  );
}

const digits = (s: string) => s.replace(/[^\d.]/g, "");

function RiskQuiz({ answers, onChange, error }: { answers: Record<string, number>; onChange: (a: Record<string, number>) => void; error?: string }) {
  const score = riskFromQuiz(answers);
  return (
    <fieldset className="space-y-5 rounded-3xl bg-surface-2/60 p-5">
      <legend className="sr-only">Risk profile questions</legend>
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-serif text-lg">Your comfort with risk</p>
        {score !== null && <span className="text-sm text-primary">{riskLabel(score)}</span>}
      </div>
      {RISK_QUIZ.map((q, qi) => (
        <div key={q.id} className="space-y-2" role="radiogroup" aria-label={q.question}>
          <p className="text-sm font-medium">
            {qi + 1}. {q.question}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {q.options.map((opt, oi) => {
              const active = answers[q.id] === oi;
              return (
                <button
                  key={opt}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => onChange({ ...answers, [q.id]: oi })}
                  className={cn(
                    "rounded-xl border px-3 py-2 text-left text-[13px] transition-colors",
                    active ? "border-teal bg-teal-mist text-teal-ink" : "border-border bg-surface hover:border-border-strong",
                  )}
                >
                  {opt}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {error && <p className="text-[13px] text-danger">{error}</p>}
    </fieldset>
  );
}

export function ProfileFields({
  value,
  onChange,
  errors,
  lockSensitive = false,
  riskMode = "slider",
}: {
  value: InvestorProfile;
  onChange: (v: InvestorProfile) => void;
  errors: ProfileErrors;
  /** Income and outflows need password re-verification once set. */
  lockSensitive?: boolean;
  riskMode?: "quiz" | "slider";
}) {
  const set = <K extends keyof InvestorProfile>(k: K, val: InvestorProfile[K]) => onChange({ ...value, [k]: val });
  const surplus =
    value.monthly_income === ""
      ? null
      : money(value.monthly_income) - money(value.monthly_emi) - money(value.rent_paid) - money(value.education_monthly);

  return (
    <div className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="age" label="Age" error={errors.age}>
          <Input inputMode="numeric" placeholder="32" value={value.age} onChange={(e) => set("age", e.target.value.replace(/[^\d]/g, ""))} />
        </Field>
        <Field id="income" label="Monthly income (after tax)" error={errors.monthly_income}>
          <RupeeInput placeholder="85000" disabled={lockSensitive} value={value.monthly_income} onChange={(e) => set("monthly_income", digits(e.target.value))} />
        </Field>
      </div>

      <div className="space-y-3">
        <p className="text-sm font-medium">Fixed monthly payments</p>
        <div className="grid gap-5 sm:grid-cols-3">
          <Field id="emi" label="EMIs" hint="All loans combined" error={errors.monthly_emi}>
            <RupeeInput placeholder="0" disabled={lockSensitive} value={value.monthly_emi} onChange={(e) => set("monthly_emi", digits(e.target.value))} />
          </Field>
          <Field id="rent-paid" label="Rent you pay" error={errors.rent_paid}>
            <RupeeInput placeholder="0" disabled={lockSensitive} value={value.rent_paid} onChange={(e) => set("rent_paid", digits(e.target.value))} />
          </Field>
          <Field id="education" label="Education fees" hint="Per month, on average" error={errors.education_monthly}>
            <RupeeInput placeholder="0" disabled={lockSensitive} value={value.education_monthly} onChange={(e) => set("education_monthly", digits(e.target.value))} />
          </Field>
        </div>
        {money(value.education_monthly) > 0 && (
          <Field id="edu-end" label="Fees end in (year)" hint="Optional. Your surplus grows after this." error={errors.education_end_year} className="sm:max-w-56">
            <Input inputMode="numeric" placeholder={String(THIS_YEAR + 6)} value={value.education_end_year} onChange={(e) => set("education_end_year", e.target.value.replace(/[^\d]/g, ""))} />
          </Field>
        )}
        {surplus !== null && (
          <p className="text-[13px] text-muted-foreground">
            Left after fixed payments: <span className={cn("tabular font-medium", surplus >= 0 ? "text-foreground" : "text-danger")}>{formatINR(surplus, { compact: false })}</span> a month
          </p>
        )}
      </div>

      <div className="flex items-center justify-between gap-4 rounded-2xl bg-surface-2 px-4 py-3.5">
        <div>
          <p className="text-sm font-medium" id="efund-label">
            I have an emergency fund
          </p>
          <p className="text-[13px] text-muted-foreground">At least 3–6 months of expenses set aside.</p>
        </div>
        <Switch aria-labelledby="efund-label" checked={value.has_emergency_fund} disabled={lockSensitive} onCheckedChange={(c) => set("has_emergency_fund", c)} />
      </div>

      {riskMode === "quiz" ? (
        <RiskQuiz answers={value.risk_answers} onChange={(a) => set("risk_answers", a)} error={errors.risk_answers} />
      ) : (
        <div className="space-y-3">
          <div className="flex items-baseline justify-between">
            <p className="text-sm font-medium" id="risk-label">
              Comfort with risk
            </p>
            <span className="text-sm text-primary">{riskLabel(value.risk_tolerance)}</span>
          </div>
          <Slider aria-labelledby="risk-label" aria-label="Comfort with risk" min={0} max={1} step={0.05} value={[value.risk_tolerance]} onValueChange={([v]) => set("risk_tolerance", v)} />
          <div className="flex justify-between text-xs text-subtle-foreground">
            <span>A 20% drop would keep me up at night</span>
            <span>I'd buy the dip</span>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <div className="flex items-baseline justify-between">
          <p className="text-sm font-medium" id="horizon-label">
            When you'll need this money
          </p>
          <span className="tabular text-sm text-primary">in {value.investment_horizon} years</span>
        </div>
        <Slider aria-labelledby="horizon-label" aria-label="Investment horizon in years" min={1} max={40} step={1} value={[value.investment_horizon]} onValueChange={([v]) => set("investment_horizon", v)} />
      </div>

      <fieldset>
        <legend className="mb-3 text-sm font-medium">Investing style</legend>
        <div className="grid gap-3 sm:grid-cols-3">
          {STRATEGIES.map((s) => {
            const active = value.financial_strategy === s.value;
            return (
              <button
                type="button"
                key={s.value}
                aria-pressed={active}
                onClick={() => set("financial_strategy", s.value)}
                className={cn("relative rounded-2xl border p-4 text-left transition-all", active ? "border-teal bg-teal-mist" : "border-border bg-surface hover:border-border-strong")}
              >
                {active && <Check className="absolute right-3 top-3 size-4 text-primary" />}
                <p className={cn("text-sm font-medium", active && "text-teal-ink")}>{s.label}</p>
                <p className="mt-1 text-xs text-muted-foreground">{s.hint}</p>
              </button>
            );
          })}
        </div>
      </fieldset>

      <Field id="goal" label="Main goal">
        <Select value={value.goal} onValueChange={(g) => set("goal", g)} options={GOALS.map((g) => ({ value: g, label: g }))} />
      </Field>
    </div>
  );
}
