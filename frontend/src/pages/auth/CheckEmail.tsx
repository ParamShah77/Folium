import { Link, useLocation } from "react-router-dom";
import { Inbox, MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/primitives";
import { useAppConfig } from "@/lib/queries";

export default function CheckEmail() {
  const email = (useLocation().state as { email?: string } | null)?.email;
  const { data: config } = useAppConfig();

  return (
    <div className="text-center">
      <span className="mx-auto flex size-16 items-center justify-center rounded-3xl bg-teal-mist text-primary">
        <MailCheck className="size-7" />
      </span>
      <h1 className="mt-6 text-[2rem] leading-tight">Check your email</h1>
      <p className="mt-3 leading-relaxed text-muted-foreground">
        We sent a verification link to {email ? <span className="font-medium text-foreground">{email}</span> : "your inbox"}.
        Open it to activate your account. The link expires in 24 hours.
      </p>

      {config?.dev_mailbox && (
        <Alert tone="info" className="mt-8 text-left" icon={<Inbox />} title="Running locally">
          No email service is configured, so messages are kept in the development inbox instead.
        </Alert>
      )}

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
      <p className="mt-6 text-[13px] text-subtle-foreground">
        Didn't get it? Registering again with the same email sends a fresh link.
      </p>
    </div>
  );
}
