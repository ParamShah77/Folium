import * as React from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export function AuthHeading({ title, subtitle }: { title: React.ReactNode; subtitle?: React.ReactNode }) {
  return (
    <div className="mb-8 space-y-2">
      <h1 className="text-[2rem] leading-tight">{title}</h1>
      {subtitle && <p className="text-[15px] leading-relaxed text-muted-foreground">{subtitle}</p>}
    </div>
  );
}

export const PasswordInput = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    const [show, setShow] = React.useState(false);
    return (
      <div className="relative">
        <Input ref={ref} type={show ? "text" : "password"} className={cn("pr-11", className)} {...props} />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg p-2 text-muted-foreground transition-colors hover:text-foreground"
          aria-label={show ? "Hide password" : "Show password"}
        >
          {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
    );
  },
);
PasswordInput.displayName = "PasswordInput";

/**
 * A rough, local guide only. The server is the authority: it scores with
 * zxcvbn and rejects anything below 3, and its message is shown verbatim.
 */
export function passwordScore(pw: string): number {
  if (!pw) return 0;
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return Math.min(4, Math.max(1, score - 1));
}

export function PasswordMeter({ password }: { password: string }) {
  const score = passwordScore(password);
  const labels = ["", "Weak", "Fair", "Good", "Strong"];
  const colors = ["", "bg-danger", "bg-peach", "bg-teal", "bg-primary"];
  if (!password) return null;
  return (
    <div className="space-y-1.5" aria-live="polite">
      <div className="flex gap-1.5">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={cn("h-1 flex-1 rounded-full transition-colors", i <= score ? colors[score] : "bg-surface-2")} />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {labels[score]} · use 12+ characters and avoid names or common words
      </p>
    </div>
  );
}

/** Where Google sign-in starts. Google sends the browser back to /auth/google. */
export function googleLoginHref({ remember = false, next }: { remember?: boolean; next?: string } = {}) {
  const q = new URLSearchParams();
  if (remember) q.set("remember", "true");
  if (next && next !== "/app") q.set("next", next);
  const qs = q.toString();
  return `/v1/auth/google/login${qs ? `?${qs}` : ""}`;
}

export function GoogleButton(props: { remember?: boolean; next?: string }) {
  return (
    <a
      href={googleLoginHref(props)}
      className="flex h-11 w-full items-center justify-center gap-3 rounded-full border border-border-strong bg-surface text-sm font-medium transition-colors hover:bg-surface-2"
    >
      <svg viewBox="0 0 24 24" className="size-[18px]" aria-hidden>
        <path fill="#4285F4" d="M22.6 12.2c0-.8-.1-1.5-.2-2.2H12v4.2h5.9a5 5 0 0 1-2.2 3.3v2.7h3.5c2.1-1.9 3.4-4.7 3.4-8z" />
        <path fill="#34A853" d="M12 23c3 0 5.4-1 7.2-2.7l-3.5-2.7c-1 .7-2.2 1.1-3.7 1.1-2.9 0-5.3-1.9-6.2-4.5H2.2v2.8A11 11 0 0 0 12 23z" />
        <path fill="#FBBC05" d="M5.8 14.2a6.6 6.6 0 0 1 0-4.3V7.1H2.2a11 11 0 0 0 0 9.9l3.6-2.8z" />
        <path fill="#EA4335" d="M12 5.4c1.6 0 3.1.6 4.2 1.7l3.1-3.1A11 11 0 0 0 2.2 7.1l3.6 2.8C6.7 7.3 9.1 5.4 12 5.4z" />
      </svg>
      Continue with Google
    </a>
  );
}

export function OrDivider() {
  return (
    <div className="my-6 flex items-center gap-3 text-xs text-subtle-foreground">
      <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
    </div>
  );
}
