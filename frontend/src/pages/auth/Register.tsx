import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, Field, Input } from "@/components/ui/primitives";
import {
  EMPTY_PROFILE,
  ProfileFields,
  profilePayload,
  validateProfile,
  type InvestorProfile,
  type ProfileErrors,
} from "@/components/profile-fields";
import { api, errorMessage } from "@/lib/api";
import { useAppConfig } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { AuthHeading, GoogleButton, OrDivider, PasswordInput, PasswordMeter } from "./shared";

interface Account {
  name: string;
  email: string;
  password: string;
}
type AccountErrors = Partial<Record<keyof Account, string>>;

function validateAccount(a: Account): AccountErrors {
  const e: AccountErrors = {};
  if (!a.name.trim()) e.name = "Enter your name";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(a.email.trim())) e.email = "Enter a valid email address";
  if (a.password.length < 8) e.password = "Use at least 8 characters";
  return e;
}

function Steps({ step }: { step: 1 | 2 }) {
  return (
    <ol className="mb-8 flex items-center gap-3 text-[13px]" aria-label="Sign-up progress">
      {[
        [1, "Account"],
        [2, "Investor profile"],
      ].map(([n, label]) => (
        <li key={n} className="flex items-center gap-2">
          <span
            className={cn(
              "flex size-6 items-center justify-center rounded-full text-xs font-medium",
              step >= (n as number) ? "bg-primary text-primary-foreground" : "bg-surface-2 text-muted-foreground",
            )}
            aria-current={step === n ? "step" : undefined}
          >
            {n}
          </span>
          <span className={step === n ? "font-medium text-foreground" : "text-muted-foreground"}>{label}</span>
          {n === 1 && <span className="mx-1 h-px w-8 bg-border" />}
        </li>
      ))}
    </ol>
  );
}

export default function Register() {
  const navigate = useNavigate();
  const { data: config } = useAppConfig();
  const [step, setStep] = React.useState<1 | 2>(1);
  const [account, setAccount] = React.useState<Account>({ name: "", email: "", password: "" });
  const [accountErrors, setAccountErrors] = React.useState<AccountErrors>({});
  const [profile, setProfile] = React.useState<InvestorProfile>(EMPTY_PROFILE);
  const [profileErrors, setProfileErrors] = React.useState<ProfileErrors>({});
  const [submitError, setSubmitError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  function next(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateAccount(account);
    setAccountErrors(errs);
    if (Object.keys(errs).length === 0) setStep(2);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateProfile(profile, { requireQuiz: true });
    setProfileErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setSubmitError(undefined);
    try {
      await api.post("/auth/register", {
        name: account.name.trim(),
        email: account.email.trim(),
        password: account.password,
        ...profilePayload(profile),
      });
      navigate("/check-email", { state: { email: account.email.trim() } });
    } catch (err) {
      const msg = errorMessage(err);
      setSubmitError(msg);
      // Password and duplicate-email problems belong to step 1.
      if (/password|email/i.test(msg)) {
        setStep(1);
        setAccountErrors(/password/i.test(msg) ? { password: msg } : { email: msg });
      }
    } finally {
      setBusy(false);
    }
  }

  const setA = (k: keyof Account) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setAccount({ ...account, [k]: e.target.value });
    setAccountErrors({ ...accountErrors, [k]: undefined });
  };

  if (step === 1) {
    return (
      <>
        <Steps step={1} />
        <AuthHeading title="Create your free account" subtitle="It takes about two minutes. Your data stays private to you." />
        {config?.google_oauth && (
          <>
            <GoogleButton />
            <OrDivider />
          </>
        )}
        <form onSubmit={next} className="space-y-5" noValidate>
          <Field id="name" label="Full name" error={accountErrors.name}>
            <Input autoComplete="name" placeholder="Ananya Iyer" value={account.name} onChange={setA("name")} />
          </Field>
          <Field id="email" label="Email" error={accountErrors.email}>
            <Input type="email" autoComplete="email" placeholder="you@example.com" value={account.email} onChange={setA("email")} />
          </Field>
          <div className="space-y-2.5">
            <Field id="password" label="Password" error={accountErrors.password}>
              <PasswordInput autoComplete="new-password" value={account.password} onChange={setA("password")} />
            </Field>
            <PasswordMeter password={account.password} />
          </div>
          <Button type="submit" className="w-full" size="lg">
            Continue <ArrowRight />
          </Button>
          <TrustLine />
        </form>
        <p className="mt-8 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Log in
          </Link>
        </p>
      </>
    );
  }

  return (
    <>
      <Steps step={2} />
      <AuthHeading
        title="About you as an investor"
        subtitle="Your analyses and projections are personalised with these. You can change them any time."
      />
      <form onSubmit={submit} className="space-y-7" noValidate>
        {submitError && <Alert tone="danger">{submitError}</Alert>}
        <ProfileFields value={profile} onChange={setProfile} errors={profileErrors} riskMode="quiz" />
        <div className="flex gap-3">
          <Button type="button" variant="outline" size="lg" onClick={() => setStep(1)}>
            <ArrowLeft /> Back
          </Button>
          <Button type="submit" size="lg" className="flex-1" loading={busy}>
            Create account
          </Button>
        </div>
        <TrustLine />
      </form>
    </>
  );
}

function TrustLine() {
  return (
    <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
      <Lock className="mt-0.5 size-3.5 shrink-0 text-primary" />
      Your data is isolated to your account and never sold or shared.{" "}
      <Link to="/privacy" className="text-primary hover:underline">
        Privacy policy
      </Link>
    </p>
  );
}
