import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAppConfig } from "@/lib/queries";
import { relativeTime } from "@/lib/utils";

interface Message {
  to: string;
  subject: string;
  body: string;
  link: string | null;
  sent_at: string;
}

/** Keep links inside this app, whatever host the backend thinks it is on. */
function inAppPath(link: string) {
  try {
    const u = new URL(link);
    return u.pathname + u.search;
  } catch {
    return link;
  }
}

export default function DevMailbox() {
  const { data: config, isPending: configPending } = useAppConfig();
  const enabled = Boolean(config?.dev_mailbox);
  const inbox = useQuery({
    queryKey: ["dev-mailbox"],
    enabled,
    refetchInterval: 4000,
    queryFn: async () => (await api.get<{ messages: Message[] }>("/dev/mailbox")).data.messages,
  });

  if (!configPending && !enabled) {
    return (
      <>
        <h1 className="text-[2rem]">Inbox unavailable</h1>
        <p className="mt-3 text-muted-foreground">
          The development inbox only exists when the server runs locally without an email service.
        </p>
        <Button asChild className="mt-8">
          <Link to="/login">Back to log in</Link>
        </Button>
      </>
    );
  }

  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-2xl bg-teal-mist text-primary">
            <Inbox className="size-5" />
          </span>
          <div>
            <h1 className="text-2xl">Development inbox</h1>
            <p className="text-sm text-muted-foreground">Emails the server would have sent</p>
          </div>
        </div>
        <Button variant="ghost" size="icon" aria-label="Refresh" onClick={() => inbox.refetch()}>
          <RefreshCw className={inbox.isFetching ? "animate-spin" : ""} />
        </Button>
      </div>

      <Alert tone="warning" className="mb-5">
        Local development only. With a real email service configured, this page disappears.
      </Alert>

      {inbox.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : inbox.data?.length ? (
        <ul className="space-y-3">
          {inbox.data.map((m) => (
            <li key={m.sent_at + m.to} className="rounded-2xl border border-border bg-surface p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">{m.subject}</p>
                  <p className="truncate text-[13px] text-muted-foreground">To {m.to}</p>
                </div>
                <span className="shrink-0 text-xs text-subtle-foreground">{relativeTime(m.sent_at)}</span>
              </div>
              {m.link && (
                <Button asChild size="sm" variant="soft" className="mt-3">
                  <Link to={inAppPath(m.link)}>
                    Open link <ArrowUpRight />
                  </Link>
                </Button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-2xl bg-surface-2 px-4 py-8 text-center text-sm text-muted-foreground">
          No emails yet. Sign up or request a password reset and they'll appear here.
        </p>
      )}
    </>
  );
}
