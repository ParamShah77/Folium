import * as React from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CircleCheck, CircleX, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

type State = { kind: "loading" } | { kind: "ok" } | { kind: "error"; message: string };

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = React.useState<State>({ kind: "loading" });
  // The token is single-use. React's StrictMode runs effects twice in
  // development, and a second call would report a false "expired link".
  const sent = React.useRef(false);

  React.useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    if (!token) {
      setState({ kind: "error", message: "This link is missing its token." });
      return;
    }
    api
      .get("/auth/verify-email", { params: { token } })
      .then(() => setState({ kind: "ok" }))
      .catch((err) => setState({ kind: "error", message: errorMessage(err, "This link is invalid or has expired.") }));
  }, [token]);

  return (
    <div className="text-center">
      {state.kind === "loading" && (
        <>
          <Loader2 className="mx-auto size-10 animate-spin text-primary" />
          <h1 className="mt-6 text-[2rem]">Verifying your email…</h1>
        </>
      )}
      {state.kind === "ok" && (
        <>
          <span className="mx-auto flex size-16 items-center justify-center rounded-3xl bg-success-mist text-success">
            <CircleCheck className="size-8" />
          </span>
          <h1 className="mt-6 text-[2rem]">You're verified</h1>
          <p className="mt-3 text-muted-foreground">Your account is active. Log in to analyse your first decision.</p>
          <Button asChild size="lg" className="mt-8 w-full">
            <Link to="/login">Log in</Link>
          </Button>
        </>
      )}
      {state.kind === "error" && (
        <>
          <span className="mx-auto flex size-16 items-center justify-center rounded-3xl bg-danger-mist text-danger">
            <CircleX className="size-8" />
          </span>
          <h1 className="mt-6 text-[2rem]">That link didn't work</h1>
          <p className="mt-3 text-muted-foreground">{state.message}</p>
          <div className="mt-8 flex flex-col gap-3">
            <Button asChild size="lg">
              <Link to="/register">Register again for a new link</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/login">Back to log in</Link>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
