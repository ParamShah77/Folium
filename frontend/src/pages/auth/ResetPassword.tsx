import * as React from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Alert, Field } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { AuthHeading, PasswordInput, PasswordMeter } from "./shared";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [errors, setErrors] = React.useState<{ password?: string; confirm?: string; form?: string }>({});
  const [busy, setBusy] = React.useState(false);

  if (!token) {
    return (
      <>
        <AuthHeading title="This link is incomplete" subtitle="Request a new reset link and open it from the email." />
        <Button asChild size="lg" className="w-full">
          <Link to="/forgot-password">Request a new link</Link>
        </Button>
      </>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (password.length < 8) next.password = "Use at least 8 characters";
    if (confirm !== password) next.confirm = "The passwords don't match";
    setErrors(next);
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      toast.success("Password updated. Log in with your new password.");
      navigate("/login", { replace: true });
    } catch (err) {
      const msg = errorMessage(err, "This link is invalid or has expired.");
      setErrors(/password/i.test(msg) && !/token|link/i.test(msg) ? { password: msg } : { form: msg });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AuthHeading title="Choose a new password" subtitle="You'll be signed out of every other device." />
      <form onSubmit={submit} className="space-y-5" noValidate>
        {errors.form && (
          <Alert tone="danger">
            {errors.form}{" "}
            <Link to="/forgot-password" className="font-medium underline underline-offset-2">
              Request a new link
            </Link>
          </Alert>
        )}
        <div className="space-y-2.5">
          <Field id="password" label="New password" error={errors.password}>
            <PasswordInput autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <PasswordMeter password={password} />
        </div>
        <Field id="confirm" label="Confirm new password" error={errors.confirm}>
          <PasswordInput autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </Field>
        <Button type="submit" size="lg" className="w-full" loading={busy}>
          Update password
        </Button>
      </form>
    </>
  );
}
