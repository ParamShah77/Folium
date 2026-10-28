import * as React from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CircleAlert, Clock } from "lucide-react";
import { LogoMark } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/primitives";
import { api, apiErrorCode, errorMessage } from "@/lib/api";
import { useAuth } from "@/providers/auth";
import { MfaStep } from "./Login";
import { AuthHeading, GoogleButton } from "./shared";

/**
 * Where Google sign-in lands (Phase C1). The backend's callback redirects
 * here with the outcome in the URL fragment, e.g. `#result=ok&next=/app`.
 * A fragment never reaches a server, so the single-use tokens it may carry
 * stay out of logs; it is cleared from the address bar as soon as it's read.
 */
export type GoogleOutcome =
  | { result: "ok"; next: string; isNew: boolean }
  | { result: "mfa"; token: string; remember: boolean; next: string }
  | { result: "deleted"; token: string; purge: string | null; remember: boolean; next: string }
  | { result: "error"; code: string };

const ERROR_TEXT: Record<string, string> = {
  OAUTH_CANCELLED: "Google sign-in was cancelled. Nothing was changed.",
  OAUTH_STATE_INVALID: "That sign-in link expired or was already used. Please try again.",
  OAUTH_EXCHANGE_FAILED: "Google didn't confirm the sign-in. Please try again.",
  OAUTH_EMAIL_UNVERIFIED: "Google hasn't verified this email address, so it can't be used to sign in here.",
  OAUTH_ACCOUNT_MISMATCH: "This email is already linked to a different Google account. Log in with your password instead.",
  OAUTH_NOT_CONFIGURED: "Google sign-in isn't available right now. Log in with your email and password.",
};

/** An in-app path only, mirroring the server's own check. */
function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/app";
}

export function parseGoogleOutcome(hash: string): GoogleOutcome | null {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const next = safeNext(p.get("next"));
  const remember = p.get("remember") === "1";
  const token = p.get("token") ?? "";
  switch (p.get("result")) {
    case "ok":
      return { result: "ok", next, isNew: p.get("new") === "1" };
    case "mfa":
      return token ? { result: "mfa", token, remember, next } : null;
    case "deleted":
      return token ? { result: "deleted", token, purge: p.get("purge"), remember, next } : null;
    case "error":
      return { result: "error", code: p.get("code") ?? "OAUTH_EXCHANGE_FAILED" };
    default:
      return null;
  }
}

export function googleErrorText(code: string): string {
  return ERROR_TEXT[code] ?? "Google sign-in didn't work. Please try again.";
}

function Finishing() {
  return (
    <div className="flex flex-col items-center gap-4 py-10 text-sm text-muted-foreground" role="status">
      <LogoMark className="size-10 animate-soft-pulse" />
      Signing you in…
    </div>
  );
}

export default function GoogleReturn() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  // Read once: the fragment is wiped from the address bar straight after.
  const [outcome] = React.useState(() => parseGoogleOutcome(window.location.hash));
  const [mfaToken, setMfaToken] = React.useState<string>();
  const [keeping, setKeeping] = React.useState(false);
  const [error, setError] = React.useState<{ text: string; expired: boolean }>();

  React.useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }, []);

  React.useEffect(() => {
    if (outcome?.result !== "ok") return;
    let cancelled = false;
    (async () => {
      await refreshUser(); // the session cookies arrived with the redirect
      if (cancelled) return;
      if (outcome.isNew) toast.success("Welcome to Folium");
      navigate(outcome.next, { replace: true });
    })();
    return () => {
      cancelled = true;
    };
  }, [outcome, navigate, refreshUser]);

  if (!outcome) return <Navigate to="/login" replace />;
  if (outcome.result === "ok") return <Finishing />;

  if (outcome.result === "mfa" || mfaToken) {
    const remember = outcome.result === "error" ? false : outcome.remember;
    const next = outcome.result === "error" ? "/app" : outcome.next;
    return (
      <MfaStep
        tempToken={mfaToken ?? (outcome.result === "mfa" ? outcome.token : "")}
        remember={remember}
        onDone={() => navigate(next, { replace: true })}
        onBack={() => navigate("/login", { replace: true })}
      />
    );
  }

  if (outcome.result === "deleted") {
    const date = outcome.purge
      ? ` on ${new Date(outcome.purge).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}`
      : "";

    async function keep() {
      if (outcome?.result !== "deleted") return;
      setKeeping(true);
      setError(undefined);
      try {
        const { data } = await api.post("/auth/google/keep-account", {
          token: outcome.token,
          remember_me: outcome.remember,
        });
        toast.success("Your account is kept.");
        if (data.mfa_required) return setMfaToken(data.temp_token);
        await refreshUser();
        navigate(outcome.next, { replace: true });
      } catch (err) {
        setError({ text: errorMessage(err), expired: apiErrorCode(err) === "OAUTH_STATE_INVALID" });
      } finally {
        setKeeping(false);
      }
    }

    return (
      <>
        <AuthHeading title="Your account is scheduled for deletion" />
        <Alert tone="warning" icon={<Clock />}>
          It will be deleted{date}. Until then you can keep it, with everything as you left it.
        </Alert>
        {error && (
          <Alert tone="danger" className="mt-4">
            {error.text}
          </Alert>
        )}
        <div className="mt-6 space-y-3">
          {error?.expired ? (
            <GoogleButton remember={outcome.remember} next={outcome.next} />
          ) : (
            <Button className="w-full" size="lg" loading={keeping} onClick={keep}>
              Keep my account
            </Button>
          )}
          <Button variant="ghost" className="w-full" onClick={() => navigate("/", { replace: true })}>
            Not now
          </Button>
        </div>
      </>
    );
  }

  return (
    <>
      <AuthHeading title="Couldn't sign in with Google" />
      <Alert tone={outcome.code === "OAUTH_CANCELLED" ? "warning" : "danger"} icon={<CircleAlert />}>
        {googleErrorText(outcome.code)}
      </Alert>
      <div className="mt-6 space-y-3">
        {outcome.code !== "OAUTH_NOT_CONFIGURED" && outcome.code !== "OAUTH_ACCOUNT_MISMATCH" && <GoogleButton />}
        <p className="text-center text-sm text-muted-foreground">
          <Link to="/login" className="font-medium text-primary hover:underline">
            Back to log in
          </Link>
        </p>
      </div>
    </>
  );
}
