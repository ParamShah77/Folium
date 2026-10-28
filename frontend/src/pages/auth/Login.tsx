import * as React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { KeyRound, MailWarning } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, Field, Input } from "@/components/ui/primitives";
import { api, apiErrorBody, apiErrorCode, errorMessage } from "@/lib/api";
import { useAppConfig } from "@/lib/queries";
import { useAuth } from "@/providers/auth";
import { AuthHeading, GoogleButton, OrDivider, PasswordInput } from "./shared";

const schema = z.object({
  email: z.string().trim().email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});
type Values = z.infer<typeof schema>;

export function MfaStep({ tempToken, remember, onDone, onBack }: { tempToken: string; remember: boolean; onDone: () => void; onBack: () => void }) {
  const { loginMfa } = useAuth();
  const [code, setCode] = React.useState("");
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return setError("Enter the code from your authenticator app");
    setBusy(true);
    setError(undefined);
    try {
      const res = await loginMfa(tempToken, code.trim(), remember);
      if (res.kind === "ok" && res.warning) toast.warning(res.warning);
      onDone();
    } catch (err) {
      setError(errorMessage(err, "That code didn't work. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AuthHeading
        title="Two-step verification"
        subtitle="Enter the 6-digit code from your authenticator app, or one of your backup codes."
      />
      <form onSubmit={submit} className="space-y-5" noValidate>
        <Field id="totp" label="Verification code" error={error}>
          <Input
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            placeholder="123 456"
            value={code}
            onChange={(e) => {
              setCode(e.target.value);
              setError(undefined);
            }}
            className="tabular text-center text-lg tracking-[0.3em]"
          />
        </Field>
        <Button type="submit" className="w-full" size="lg" loading={busy}>
          Verify and continue
        </Button>
        <Button type="button" variant="ghost" className="w-full" onClick={onBack}>
          Use a different account
        </Button>
      </form>
    </>
  );
}

export default function Login() {
  const { login } = useAuth();
  const { data: config } = useAppConfig();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/app";
  const [formError, setFormError] = React.useState<{ text: string; unverified?: boolean; deletion?: string | null }>();
  const [keeping, setKeeping] = React.useState(false);
  const [mfaToken, setMfaToken] = React.useState<string>();
  const [remember, setRemember] = React.useState(false);

  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  async function onSubmit(values: Values) {
    setFormError(undefined);
    try {
      const res = await login(values.email, values.password, remember);
      if (res.kind === "mfa") return setMfaToken(res.tempToken);
      toast.success(`Welcome back, ${res.user.name.split(" ")[0]}`);
      navigate(from, { replace: true });
    } catch (err) {
      const code = apiErrorCode(err);
      const purge = code === "ACCOUNT_DELETED" ? ((apiErrorBody(err)?.purge_after as string | null) ?? null) : undefined;
      const date = purge
        ? ` on ${new Date(purge).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}`
        : "";
      setFormError({
        text:
          code === "INVALID_CREDENTIALS"
            ? "That email and password don't match."
            : code === "ACCOUNT_DELETED"
              ? `This account is scheduled for deletion${date}.`
              : errorMessage(err),
        unverified: code === "EMAIL_NOT_VERIFIED",
        deletion: purge,
      });
    }
  }

  async function keepAccount() {
    setKeeping(true);
    const values = form.getValues();
    try {
      await api.post("/auth/cancel-deletion", { email: values.email, password: values.password });
      toast.success("Your account is kept.");
      await onSubmit(values);
    } catch (err) {
      setFormError({ text: errorMessage(err) });
    } finally {
      setKeeping(false);
    }
  }

  if (mfaToken) {
    return (
      <MfaStep
        tempToken={mfaToken}
        remember={remember}
        onDone={() => navigate(from, { replace: true })}
        onBack={() => {
          setMfaToken(undefined);
          form.reset();
        }}
      />
    );
  }

  const { errors, isSubmitting } = form.formState;

  return (
    <>
      <AuthHeading title="Welcome back" subtitle="Log in to review your decisions and analyse new ones." />

      {config?.google_oauth && (
        <>
          <GoogleButton remember={remember} next={from} />
          <OrDivider />
        </>
      )}

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {formError && (
          <Alert tone={formError.unverified ? "warning" : "danger"} icon={formError.unverified ? <MailWarning /> : <KeyRound />}>
            {formError.text}{" "}
            {formError.unverified && (
              <Link className="font-medium underline underline-offset-2" to="/check-email" state={{ email: form.getValues("email") }}>
                Find your verification email
              </Link>
            )}
            {formError.deletion !== undefined && (
              <Button type="button" size="sm" variant="outline" className="mt-3" loading={keeping} onClick={keepAccount}>
                Keep my account
              </Button>
            )}
          </Alert>
        )}
        <Field id="email" label="Email" error={errors.email?.message}>
          <Input type="email" autoComplete="email" placeholder="you@example.com" {...form.register("email")} />
        </Field>
        <Field
          id="password"
          label="Password"
          error={errors.password?.message}
          trailing={
            <Link to="/forgot-password" className="text-[13px] text-primary hover:underline">
              Forgot password?
            </Link>
          }
        >
          <PasswordInput autoComplete="current-password" {...form.register("password")} />
        </Field>
        <label className="flex cursor-pointer items-center gap-2.5 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="size-4 rounded border-border-strong accent-[var(--primary)]"
          />
          Keep me signed in on this device
        </label>
        <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>
          Log in
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-muted-foreground">
        New to Folium?{" "}
        <Link to="/register" className="font-medium text-primary hover:underline">
          Create an account
        </Link>
      </p>
    </>
  );
}
