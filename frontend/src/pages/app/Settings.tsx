import * as React from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { toast } from "sonner";
import { Check, Copy, Database, Download, KeyRound, Lock, Monitor, Moon, Palette, ShieldCheck, Sun, Trash2, UserRound } from "lucide-react";
import { PageHeader } from "@/components/layouts";
import {
  ProfileFields,
  RupeeInput,
  profilePayload,
  validateProfile,
  type InvestorProfile,
  type ProfileErrors,
} from "@/components/profile-fields";
import { Button } from "@/components/ui/button";
import { Alert, Badge, Card, CardContent, CardDescription, CardHeader, CardTitle, Field, Input, Skeleton, Switch } from "@/components/ui/primitives";
import { Dialog, DialogContent, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/overlays";
import { PasswordInput, PasswordMeter } from "@/pages/auth/shared";
import { api, apiErrorCode, errorMessage } from "@/lib/api";
import { useAppConfig, useProfile } from "@/lib/queries";
import type { Profile, Strategy } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth";
import { useTheme } from "@/providers/theme";

/* ------------------------------------------------------------------ */
/* Accounts made with Google (no password until one is set)           */
/* ------------------------------------------------------------------ */

/** False only for an account made with Google that has no password yet. */
function useHasPassword() {
  return useAuth().user?.has_password !== false;
}

/** Sends the usual reset link, which sets a first password just the same. */
function useSendPasswordLink() {
  const { user } = useAuth();
  const [busy, setBusy] = React.useState(false);
  const [sent, setSent] = React.useState(false);
  async function send() {
    if (!user) return;
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email: user.email });
      setSent(true);
      toast.success(`We've emailed a link to ${user.email}. It works for 15 minutes.`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return { send, busy, sent };
}

function NeedsPasswordNote({ action }: { action: string }) {
  const { send, busy, sent } = useSendPasswordLink();
  return (
    <Alert tone="info" icon={<KeyRound />}>
      You sign in with Google, so there's no password on this account yet. To {action}, set one first.
      <Button type="button" size="sm" variant="outline" className="mt-3" loading={busy} disabled={sent} onClick={send}>
        {sent ? "Link sent" : "Email me a link to set a password"}
      </Button>
    </Alert>
  );
}

/* ------------------------------------------------------------------ */
/* Profile                                                             */
/* ------------------------------------------------------------------ */

function toForm(p: Profile): InvestorProfile {
  const s = (v: number | null) => (v === null || v === undefined ? "" : String(v));
  return {
    age: s(p.age),
    monthly_income: s(p.monthly_income),
    monthly_emi: s(p.monthly_emi),
    rent_paid: s(p.rent_paid),
    education_monthly: s(p.education_monthly),
    education_end_year: s(p.education_end_year),
    has_emergency_fund: p.has_emergency_fund ?? false,
    risk_tolerance: p.risk_tolerance ?? 0.5,
    risk_answers: {},
    investment_horizon: p.investment_horizon ?? 15,
    financial_strategy: (p.financial_strategy ?? "moderate") as Strategy,
    goal: p.goal ?? "Wealth growth",
  };
}

const onlyNumber = (s: string) => s.replace(/[^\d.]/g, "");

function SecureFinancesDialog({ profile, open, onOpenChange }: { profile: Profile; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const hasPassword = useHasPassword();
  const s = (v: number | null) => (v === null || v === undefined ? "" : String(v));
  const [income, setIncome] = React.useState(s(profile.monthly_income));
  const [emi, setEmi] = React.useState(s(profile.monthly_emi));
  const [rent, setRent] = React.useState(s(profile.rent_paid));
  const [edu, setEdu] = React.useState(s(profile.education_monthly));
  const [efund, setEfund] = React.useState(Boolean(profile.has_emergency_fund));
  const [password, setPassword] = React.useState("");
  const [totp, setTotp] = React.useState("");
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!password) return setError("Enter your password to confirm");
    if (profile.mfa_enabled && !totp) return setError("Enter the code from your authenticator app");
    setBusy(true);
    setError(undefined);
    const n = (v: string) => (v === "" ? null : Number(v));
    try {
      await api.put("/users/me/profile/sensitive", {
        monthly_income: n(income),
        monthly_emi: n(emi),
        rent_paid: n(rent),
        education_monthly: n(edu),
        has_emergency_fund: efund,
        password,
        totp_code: profile.mfa_enabled ? totp : null,
      });
      await qc.invalidateQueries({ queryKey: ["profile"] });
      await qc.invalidateQueries({ queryKey: ["portfolio"] });
      toast.success("Income and payments updated");
      onOpenChange(false);
      setPassword("");
      setTotp("");
    } catch (err) {
      setError(apiErrorCode(err) === "INVALID_CREDENTIALS" ? "That password isn't right." : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Update income and payments" description="These shape every analysis, so changing them needs your password.">
        {!hasPassword ? (
          <NeedsPasswordNote action="change these" />
        ) : (
        <form onSubmit={save} className="space-y-4" noValidate>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="grid grid-cols-2 gap-4">
            <Field id="s-income" label="Monthly income">
              <RupeeInput value={income} onChange={(e) => setIncome(onlyNumber(e.target.value))} />
            </Field>
            <Field id="s-emi" label="EMIs">
              <RupeeInput value={emi} onChange={(e) => setEmi(onlyNumber(e.target.value))} />
            </Field>
            <Field id="s-rent" label="Rent you pay">
              <RupeeInput value={rent} onChange={(e) => setRent(onlyNumber(e.target.value))} />
            </Field>
            <Field id="s-edu" label="Education fees">
              <RupeeInput value={edu} onChange={(e) => setEdu(onlyNumber(e.target.value))} />
            </Field>
          </div>
          <label className="flex items-center justify-between rounded-2xl bg-surface-2 px-4 py-3 text-sm">
            I have an emergency fund
            <Switch checked={efund} onCheckedChange={setEfund} />
          </label>
          <Field id="s-password" label="Your password">
            <PasswordInput autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          {profile.mfa_enabled && (
            <Field id="s-totp" label="Authenticator code">
              <Input inputMode="numeric" autoComplete="one-time-code" value={totp} onChange={(e) => setTotp(e.target.value)} />
            </Field>
          )}
          <Button type="submit" className="w-full" loading={busy}>
            Save securely
          </Button>
        </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ProfileTab({ profile }: { profile: Profile }) {
  const qc = useQueryClient();
  const { refreshUser } = useAuth();
  const [name, setName] = React.useState(profile.name);
  const [form, setForm] = React.useState<InvestorProfile>(() => toForm(profile));
  const [errors, setErrors] = React.useState<ProfileErrors & { name?: string }>({});
  const [busy, setBusy] = React.useState(false);
  const [secureOpen, setSecureOpen] = React.useState(false);
  const financesLocked = profile.monthly_income !== null;

  React.useEffect(() => {
    // Keep the protected fields in sync after a secure update.
    const fresh = toForm(profile);
    setForm((f) => ({
      ...f,
      monthly_income: fresh.monthly_income,
      monthly_emi: fresh.monthly_emi,
      rent_paid: fresh.rent_paid,
      education_monthly: fresh.education_monthly,
      has_emergency_fund: fresh.has_emergency_fund,
    }));
  }, [profile]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const errs: ProfileErrors & { name?: string } = validateProfile(form);
    if (!name.trim()) errs.name = "Enter your name";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const payload = profilePayload(form);
      await api.put("/users/me/profile", {
        name: name.trim(),
        goal: payload.goal,
        financial_strategy: payload.financial_strategy,
        age: payload.age,
        risk_tolerance: payload.risk_tolerance,
        investment_horizon: payload.investment_horizon,
        education_end_year: payload.education_end_year,
        ...(financesLocked
          ? {}
          : {
              monthly_income: payload.monthly_income,
              monthly_emi: payload.monthly_emi,
              rent_paid: payload.rent_paid,
              education_monthly: payload.education_monthly,
              has_emergency_fund: payload.has_emergency_fund,
            }),
      });
      await qc.invalidateQueries({ queryKey: ["profile"] });
      await qc.invalidateQueries({ queryKey: ["portfolio"] });
      await refreshUser();
      toast.success("Profile saved");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="grid gap-6 lg:grid-cols-[1fr_300px]" noValidate>
      <Card>
        <CardContent className="space-y-6">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field id="name" label="Full name" error={errors.name}>
              <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </Field>
            <Field id="email" label="Email" hint="Contact support to change your email.">
              <Input value={profile.email} disabled readOnly />
            </Field>
          </div>
          <ProfileFields value={form} onChange={setForm} errors={errors} lockSensitive={financesLocked} />
          {financesLocked && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface-2/70 px-4 py-3 text-sm">
              <span className="flex items-center gap-2 text-muted-foreground">
                <Lock className="size-4" /> Income and fixed payments are protected
              </span>
              <Button type="button" size="sm" variant="soft" onClick={() => setSecureOpen(true)}>
                Update securely
              </Button>
            </div>
          )}
          <div className="flex justify-end">
            <Button type="submit" loading={busy}>
              Save changes
            </Button>
          </div>
        </CardContent>
      </Card>
      <div className="space-y-4">
        <div className="rounded-3xl bg-teal-mist p-6 text-sm leading-relaxed text-teal-ink">
          <UserRound className="size-5" />
          <p className="mt-3 font-serif text-lg leading-snug">Why we ask</p>
          <p className="mt-2 text-teal-ink/85">
            Age, comfort with risk and horizon shape your projections, which run to your horizon. Income, fixed payments and an emergency fund
            show how much financial pressure you're under when you decide.
          </p>
        </div>
        <p className="px-2 text-xs leading-relaxed text-subtle-foreground">
          Every change is written to a private change log. Only you can see your profile and analyses.
        </p>
      </div>
      <SecureFinancesDialog profile={profile} open={secureOpen} onOpenChange={setSecureOpen} />
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Security                                                            */
/* ------------------------------------------------------------------ */

function useSignOutAfter() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  return async (message: string) => {
    toast.success(message);
    await logout();
    navigate("/login", { replace: true });
  };
}

function SetPasswordCard() {
  const { send, busy, sent } = useSendPasswordLink();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-5 text-primary" /> Password
        </CardTitle>
        <CardDescription>You sign in with Google. A password is optional.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm leading-relaxed text-muted-foreground">
        <p>
          Setting one lets you log in with your email too, and confirm sensitive changes such as your income, turning
          off two-step verification or deleting your account. We'll email you a link to choose it.
        </p>
        <Button variant="outline" loading={busy} disabled={sent} onClick={send}>
          {sent ? "Link sent" : "Set a password"}
        </Button>
      </CardContent>
    </Card>
  );
}

function ChangePasswordCard({ mfa }: { mfa: boolean }) {
  const signOut = useSignOutAfter();
  const [current, setCurrent] = React.useState("");
  const [next, setNext] = React.useState("");
  const [totp, setTotp] = React.useState("");
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!current || next.length < 8) return setError("Enter your current password and a new one of 8+ characters");
    setBusy(true);
    setError(undefined);
    try {
      await api.post("/auth/change-password", {
        current_password: current,
        new_password: next,
        totp_code: mfa ? totp : null,
      });
      await signOut("Password changed. Log in with your new password.");
    } catch (err) {
      setError(apiErrorCode(err) === "INVALID_CREDENTIALS" ? "Your current password isn't right." : errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-5 text-primary" /> Password
        </CardTitle>
        <CardDescription>Changing it signs you out everywhere.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4" noValidate>
          {error && <Alert tone="danger">{error}</Alert>}
          <Field id="cur-pw" label="Current password">
            <PasswordInput autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <div className="space-y-2.5">
            <Field id="new-pw" label="New password">
              <PasswordInput autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
            </Field>
            <PasswordMeter password={next} />
          </div>
          {mfa && (
            <Field id="pw-totp" label="Authenticator code">
              <Input inputMode="numeric" autoComplete="one-time-code" value={totp} onChange={(e) => setTotp(e.target.value)} />
            </Field>
          )}
          <Button type="submit" variant="outline" loading={busy}>
            Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function MfaCard({ enabled }: { enabled: boolean }) {
  const { refreshUser } = useAuth();
  const qc = useQueryClient();
  const signOut = useSignOutAfter();
  const [setup, setSetup] = React.useState<{ secret: string; uri: string } | null>(null);
  const [code, setCode] = React.useState("");
  const [backup, setBackup] = React.useState<string[] | null>(null);
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);
  const [disableOpen, setDisableOpen] = React.useState(false);
  const [disablePw, setDisablePw] = React.useState("");
  const [disableCode, setDisableCode] = React.useState("");
  const [copied, setCopied] = React.useState(false);

  async function start() {
    setBusy(true);
    setError(undefined);
    try {
      const { data } = await api.post<{ secret: string; qr_code_url: string }>("/auth/mfa/setup");
      setSetup({ secret: data.secret, uri: data.qr_code_url });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return setError("Enter the 6-digit code");
    setBusy(true);
    setError(undefined);
    try {
      const { data } = await api.post<{ backup_codes: string[] }>("/auth/mfa/verify-setup", { totp_code: code.trim() });
      setBackup(data.backup_codes);
      setSetup(null);
      setCode("");
      await refreshUser();
      await qc.invalidateQueries({ queryKey: ["profile"] });
      toast.success("Two-step verification is on");
    } catch (err) {
      setError(errorMessage(err, "That code didn't work. Try again."));
    } finally {
      setBusy(false);
    }
  }

  async function disable(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await api.post("/auth/mfa/disable", { password: disablePw, totp_code: disableCode });
      await signOut("Two-step verification is off. Log in again.");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-primary" /> Two-step verification
          </CardTitle>
          <CardDescription>A code from an authenticator app, on top of your password.</CardDescription>
        </div>
        <Badge tone={enabled ? "success" : "neutral"}>{enabled ? "On" : "Off"}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && !disableOpen && <Alert tone="danger">{error}</Alert>}

        {backup && (
          <div className="rounded-2xl bg-warning-mist p-5">
            <p className="font-medium text-warning-ink">Save your backup codes</p>
            <p className="mt-1 text-sm text-warning-ink/85">Each works once if you lose your phone. They won't be shown again.</p>
            <ul className="tabular mt-4 grid grid-cols-2 gap-2 font-mono text-sm">
              {backup.map((c) => (
                <li key={c} className="rounded-xl bg-surface px-3 py-2 text-center">
                  {c}
                </li>
              ))}
            </ul>
            <Button
              size="sm"
              variant="outline"
              className="mt-4"
              onClick={async () => {
                await navigator.clipboard.writeText(backup.join("\n"));
                setCopied(true);
              }}
            >
              {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy codes"}
            </Button>
          </div>
        )}

        {!enabled && !setup && (
          <Button onClick={start} loading={busy}>
            Turn on
          </Button>
        )}

        {setup && (
          <form onSubmit={verify} className="grid gap-6 sm:grid-cols-[auto_1fr]">
            <div className="rounded-3xl bg-white p-4">
              <QRCodeSVG value={setup.uri} size={156} fgColor="#2f2b29" />
            </div>
            <div className="space-y-4">
              <ol className="list-decimal space-y-1.5 pl-5 text-sm text-muted-foreground">
                <li>Scan the code with Google Authenticator, Authy or 1Password.</li>
                <li>Enter the 6-digit code it shows.</li>
              </ol>
              <p className="break-all rounded-xl bg-surface-2 px-3 py-2 font-mono text-xs text-muted-foreground">{setup.secret}</p>
              <Field id="mfa-code" label="Code from the app">
                <Input inputMode="numeric" autoComplete="one-time-code" placeholder="123456" value={code} onChange={(e) => setCode(e.target.value)} />
              </Field>
              <div className="flex gap-2">
                <Button type="submit" loading={busy}>
                  Verify and turn on
                </Button>
                <Button type="button" variant="ghost" onClick={() => setSetup(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          </form>
        )}

        {enabled && !backup && (
          <Button variant="danger" onClick={() => setDisableOpen(true)}>
            Turn off
          </Button>
        )}

        <Dialog open={disableOpen} onOpenChange={setDisableOpen}>
          <DialogContent title="Turn off two-step verification?" description="Your account will be protected by your password alone. You'll be signed out.">
            <form onSubmit={disable} className="space-y-4" noValidate>
              {error && <Alert tone="danger">{error}</Alert>}
              <Field id="d-pw" label="Password">
                <PasswordInput autoComplete="current-password" value={disablePw} onChange={(e) => setDisablePw(e.target.value)} />
              </Field>
              <Field id="d-code" label="Authenticator code">
                <Input inputMode="numeric" autoComplete="one-time-code" value={disableCode} onChange={(e) => setDisableCode(e.target.value)} />
              </Field>
              <Button type="submit" variant="danger" className="w-full" loading={busy}>
                Turn off and sign out
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Your data (Phase B2)                                                */
/* ------------------------------------------------------------------ */

function ExportCard() {
  const [busy, setBusy] = React.useState(false);
  async function download() {
    setBusy(true);
    try {
      const res = await api.get("/users/me/export", { responseType: "blob" });
      const name = /filename="([^"]+)"/.exec(res.headers["content-disposition"] ?? "")?.[1] ?? "folium-my-data.json";
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Your data is downloading.");
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't prepare your data. Try again."));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="size-4 text-primary" /> Download my data
        </CardTitle>
        <CardDescription>Everything Folium holds about you, in one file.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm leading-relaxed text-muted-foreground">
        <p>
          Your profile, portfolio and every analysis, with their secure record and the steps to check it yourself.
          Your password and two-step secrets are never included.
        </p>
        <Button onClick={download} loading={busy}>
          <Download className="size-4" /> Download (JSON)
        </Button>
      </CardContent>
    </Card>
  );
}

function AiHelpCard({ consent }: { consent: boolean }) {
  const { data: config } = useAppConfig();
  const qc = useQueryClient();
  const [on, setOn] = React.useState(consent);
  const [busy, setBusy] = React.useState(false);
  async function toggle(next: boolean) {
    setBusy(true);
    try {
      await api.put("/users/me/ai-consent", { enabled: next });
      setOn(next);
      await qc.invalidateQueries({ queryKey: ["profile"] });
      toast.success(next ? "AI help is on for your next analyses." : "AI help is off.");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="lg:col-span-2">
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>AI help</CardTitle>
          <CardDescription>Let Google's Gemini read what you write and word the two sides of each analysis.</CardDescription>
        </div>
        <Switch checked={on} disabled={busy} onCheckedChange={toggle} aria-label="AI help" />
      </CardHeader>
      <CardContent className="space-y-2 text-sm leading-relaxed text-muted-foreground">
        <p>
          Off by default. Without it, your comment is read by simple rules on our server and the two sides are written
          from your numbers, and nothing is sent anywhere. With it on, your comment and the analysis numbers (not your
          name or email) are sent to Google for each new analysis. AI help never changes the recommendation, and any
          wording that adds or changes a number is thrown away.
        </p>
        {on && config && !config.ai_help && (
          <p className="text-warning-ink">AI help isn't set up on this server yet, so the rules are used for now.</p>
        )}
      </CardContent>
    </Card>
  );
}

function DeleteAccountCard({ mfa }: { mfa: boolean }) {
  const { logout } = useAuth();
  const hasPassword = useHasPassword();
  const navigate = useNavigate();
  const [open, setOpen] = React.useState(false);
  const [password, setPassword] = React.useState("");
  const [code, setCode] = React.useState("");
  const [reason, setReason] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string>();

  async function remove(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      const { data } = await api.post<{ purge_after: string }>("/users/me/delete", {
        password,
        totp_code: mfa ? code : undefined,
        reason: reason || undefined,
      });
      const when = new Date(data.purge_after).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
      toast.success(`Your account will be deleted on ${when}. Log in before then to keep it.`, { duration: 10_000 });
      await logout().catch(() => undefined); // the server has already ended the session
      navigate("/", { replace: true });
    } catch (err) {
      const c = apiErrorCode(err);
      setError(
        c === "INVALID_CREDENTIALS" ? "That password isn't right." : c === "INVALID_MFA_CODE" ? "That code didn't work." : errorMessage(err),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trash2 className="size-4 text-danger" /> Delete my account
        </CardTitle>
        <CardDescription>You'll be signed out, with 30 days to change your mind.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm leading-relaxed text-muted-foreground">
        <p>
          For 30 days you can log in and keep your account. After that, your name, email, profile, portfolio, comments
          and analysis details are erased for good. The secure record of past analyses stays, so it can't be altered,
          but it can no longer be linked to you.
        </p>
        {hasPassword ? (
          <Button variant="danger" onClick={() => setOpen(true)}>
            Delete my account
          </Button>
        ) : (
          <NeedsPasswordNote action="delete your account" />
        )}
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent title="Delete your account?" description="Confirm with your password. You'll be signed out straight away.">
            <form onSubmit={remove} className="space-y-4" noValidate>
              {error && <Alert tone="danger">{error}</Alert>}
              <Field id="del-pw" label="Password">
                <PasswordInput autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </Field>
              {mfa && (
                <Field id="del-code" label="Authenticator code">
                  <Input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />
                </Field>
              )}
              <Field id="del-reason" label="Why are you leaving? (optional)">
                <Input value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
              </Field>
              <Button type="submit" variant="danger" className="w-full" loading={busy} disabled={!password}>
                Delete, with 30 days to change my mind
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Appearance                                                          */
/* ------------------------------------------------------------------ */

function AppearanceTab() {
  const { theme, setTheme } = useTheme();
  const options = [
    { value: "light", label: "Light", icon: Sun, swatch: "bg-[#faf8f3]" },
    { value: "dark", label: "Dark", icon: Moon, swatch: "bg-[#171614]" },
    { value: "system", label: "Match my device", icon: Monitor, swatch: "bg-gradient-to-r from-[#faf8f3] to-[#171614]" },
  ] as const;
  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Theme</CardTitle>
        <CardDescription>Both themes use the same soft palette.</CardDescription>
      </CardHeader>
      <CardContent>
        <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-3">
          {options.map(({ value, label, icon: Icon, swatch }) => (
            <button
              key={value}
              role="radio"
              aria-checked={theme === value}
              onClick={() => setTheme(value)}
              className={cn(
                "rounded-2xl border p-3 text-left transition-all",
                theme === value ? "border-teal ring-4 ring-teal/15" : "border-border hover:border-border-strong",
              )}
            >
              <span className={cn("block h-16 rounded-xl border border-border", swatch)} />
              <span className="mt-3 flex items-center gap-2 text-sm font-medium">
                <Icon className="size-4 text-muted-foreground" /> {label}
              </span>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "profile";
  const { data: profile, isPending } = useProfile();
  const hasPassword = useHasPassword();

  return (
    <>
      <PageHeader eyebrow="Settings" title="Your account" description="Your investor profile, sign-in security, your data and how Folium looks." />
      <Tabs value={tab} onValueChange={(v) => setParams(v === "profile" ? {} : { tab: v }, { replace: true })}>
        <TabsList className="mb-6">
          <TabsTrigger value="profile">
            <span className="flex items-center gap-1.5"><UserRound className="size-4" /> Profile</span>
          </TabsTrigger>
          <TabsTrigger value="security">
            <span className="flex items-center gap-1.5"><ShieldCheck className="size-4" /> Security</span>
          </TabsTrigger>
          <TabsTrigger value="data">
            <span className="flex items-center gap-1.5"><Database className="size-4" /> Your data</span>
          </TabsTrigger>
          <TabsTrigger value="appearance">
            <span className="flex items-center gap-1.5"><Palette className="size-4" /> Appearance</span>
          </TabsTrigger>
        </TabsList>

        {isPending || !profile ? (
          <Skeleton className="h-96 rounded-3xl" />
        ) : (
          <>
            <TabsContent value="profile">
              <ProfileTab profile={profile} />
            </TabsContent>
            <TabsContent value="security" className="grid gap-6 lg:grid-cols-2">
              <MfaCard enabled={profile.mfa_enabled} />
              {hasPassword ? <ChangePasswordCard mfa={profile.mfa_enabled} /> : <SetPasswordCard />}
            </TabsContent>
            <TabsContent value="data" className="grid gap-6 lg:grid-cols-2">
              <ExportCard />
              <DeleteAccountCard mfa={profile.mfa_enabled} />
              <AiHelpCard consent={Boolean(profile.ai_consent)} />
            </TabsContent>
            <TabsContent value="appearance">
              <AppearanceTab />
            </TabsContent>
          </>
        )}
      </Tabs>
    </>
  );
}
