import * as React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, Field, Input } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { useAppConfig } from "@/lib/queries";
import { AuthHeading } from "./shared";

export default function ForgotPassword() {
  const { data: config } = useAppConfig();
  const [email, setEmail] = React.useState("");
  const [error, setError] = React.useState<string>();
  const [sent, setSent] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return setError("Enter a valid email address");
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email: email.trim() });
      setSent(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="text-center">
        <span className="mx-auto flex size-16 items-center justify-center rounded-3xl bg-teal-mist text-primary">
          <MailCheck className="size-7" />
        </span>
        <h1 className="mt-6 text-[2rem]">Check your email</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          If an account exists for <span className="font-medium text-foreground">{email}</span>, a reset link is on its
          way. It expires in 15 minutes.
        </p>
        <div className="mt-8 flex flex-col gap-3">
          {config?.dev_mailbox && (
            <Button asChild size="lg">
              <Link to="/dev/mailbox">Open development inbox</Link>
            </Button>
          )}
          <Button asChild variant="ghost">
            <Link to="/login">Back to log in</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <>
      <Link to="/login" className="mb-8 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to log in
      </Link>
      <AuthHeading title="Reset your password" subtitle="Enter the email you signed up with and we'll send you a link." />
      <form onSubmit={submit} className="space-y-5" noValidate>
        {error && !error.startsWith("Enter") && <Alert tone="danger">{error}</Alert>}
        <Field id="email" label="Email" error={error?.startsWith("Enter") ? error : undefined}>
          <Input
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError(undefined);
            }}
          />
        </Field>
        <Button type="submit" size="lg" className="w-full" loading={busy}>
          Send reset link
        </Button>
      </form>
    </>
  );
}
