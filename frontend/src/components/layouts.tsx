import * as React from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  ChevronDown,
  EyeOff,
  History,
  Lock,
  Wallet,
  LayoutDashboard,
  LogOut,
  Menu,
  PlusCircle,
  Settings,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Logo, ThemeToggle } from "@/components/brand";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/overlays";
import { useAuth } from "@/providers/auth";
import { useMarketRibbon } from "@/lib/queries";
import { cn, initials } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Public site                                                         */
/* ------------------------------------------------------------------ */

export function PublicLayout() {
  const { user } = useAuth();
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-40 border-b border-transparent bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
          <Logo />
          <nav className="flex items-center gap-1.5 sm:gap-3">
            <a href="/#how" className="hidden px-3 text-sm text-muted-foreground transition-colors hover:text-foreground sm:block">
              How it works
            </a>
            <a href="/#security" className="hidden px-3 text-sm text-muted-foreground transition-colors hover:text-foreground sm:block">
              Security
            </a>
            <ThemeToggle />
            {user ? (
              <Button asChild size="sm">
                <Link to="/app">Open dashboard</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/login">Log in</Link>
                </Button>
                <Button asChild variant="blush" size="sm">
                  <Link to="/register">Create account</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>
      <Outlet />
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <Logo />
          <nav className="flex flex-wrap gap-x-5 gap-y-2" aria-label="Footer">
            <Link to="/privacy" className="hover:text-foreground">Privacy policy</Link>
            <a href="/#security" className="hover:text-foreground">Security</a>
            <span>© {new Date().getFullYear()} Folium</span>
          </nav>
          <p className="text-xs">For information and education. Not investment advice.</p>
        </div>
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Auth pages: form on the left, a quiet brand panel on the right      */
/* ------------------------------------------------------------------ */

export function AuthLayout() {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,0.9fr)]">
      <div className="flex flex-col px-5 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <Logo />
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[420px] animate-fade-up">
            <Outlet />
          </div>
        </div>
      </div>
      <aside className="relative hidden overflow-hidden bg-teal-mist lg:block">
        <div className="absolute -right-24 -top-24 size-96 rounded-full bg-blush/70 blur-3xl" aria-hidden />
        <div className="absolute -bottom-32 -left-16 size-[28rem] rounded-full bg-teal/25 blur-3xl" aria-hidden />
        <div className="relative flex h-full flex-col justify-end p-14">
          <p className="max-w-md font-serif text-[2rem] leading-tight text-teal-ink">
            The most expensive investing mistakes aren't about the market. They're about the moment.
          </p>
          <p className="mt-5 max-w-sm text-[15px] leading-relaxed text-teal-ink/75">
            Folium reads the decision you're about to make, names the bias behind it, and shows what it means
            for your wealth by the time you need the money.
          </p>
          <ul className="mt-10 grid max-w-md gap-2.5">
            {[
              [Lock, "Your data is isolated to your account"],
              [ShieldCheck, "Two-step verification available"],
              [EyeOff, "Never sold, never shared, no ads"],
            ].map(([Icon, text]) => {
              const I = Icon as typeof Lock;
              return (
                <li key={text as string} className="flex items-center gap-3 rounded-2xl bg-surface/70 px-4 py-3 text-sm text-foreground backdrop-blur">
                  <I className="size-4 text-primary" /> {text as string}
                </li>
              );
            })}
          </ul>
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Signed-in app shell                                                 */
/* ------------------------------------------------------------------ */

const NAV = [
  { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/app/portfolio", label: "Portfolio", icon: Wallet, end: false },
  { to: "/app/new", label: "New analysis", icon: PlusCircle, end: false },
  { to: "/app/history", label: "History", icon: History, end: false },
  { to: "/app/settings", label: "Settings", icon: Settings, end: false },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="space-y-1" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-2xl px-3.5 py-2.5 text-[15px] transition-colors",
              isActive
                ? "bg-surface font-medium text-foreground shadow-soft"
                : "text-muted-foreground hover:bg-surface/60 hover:text-foreground",
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon className={cn("size-[18px]", isActive ? "text-primary" : "text-subtle-foreground")} />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function MarketTicker() {
  const { data } = useMarketRibbon();
  if (!data || data.indices.length === 0) return null;
  return (
    <div className="hidden items-center gap-5 overflow-hidden text-[13px] md:flex" aria-label="Market snapshot">
      {data.indices.map((i, idx) => {
        const up = (i.change_pct ?? 0) >= 0;
        const isVix = i.key === "india_vix";
        return (
          // Two indices fit beside the menu on mid-size screens; all four from xl.
          <span key={i.key} className={cn("items-center gap-1.5 whitespace-nowrap", idx < 2 ? "flex" : "hidden xl:flex")}>
            <span className="text-muted-foreground">{i.label}</span>
            <span className="tabular font-medium text-foreground">
              {i.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </span>
            {i.change_pct !== null && (
              <span
                className={cn(
                  "tabular inline-flex items-center gap-0.5",
                  isVix ? "text-muted-foreground" : up ? "text-success" : "text-danger",
                )}
              >
                {up ? <TrendingUp className="size-3.5" /> : <TrendingDown className="size-3.5" />}
                {up ? "+" : ""}
                {i.change_pct.toFixed(2)}%
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2.5 transition-colors hover:bg-surface-2">
        <span className="flex size-8 items-center justify-center rounded-full bg-blush text-xs font-semibold text-rose">
          {initials(user?.name)}
        </span>
        <span className="hidden max-w-32 truncate text-sm font-medium sm:block">{user?.name}</span>
        <ChevronDown className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>
          <p className="text-sm font-medium">{user?.name}</p>
          <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/app/settings")}>
          <Settings /> Settings
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate("/app/settings?tab=security")}>
          <ShieldCheck /> Security
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={async () => {
            // The route guard sends a deliberate logout home (see RequireAuth).
            await logout();
            toast.success("Logged out");
          }}
        >
          <LogOut /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell() {
  const [open, setOpen] = React.useState(false);
  const location = useLocation();
  React.useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[260px_1fr]">
      {/* Sidebar (desktop) */}
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-border bg-surface-2/60 px-4 py-6 lg:flex">
        <Logo to="/app" className="px-2" />
        <div className="mt-9 flex-1">
          <NavItems />
        </div>
        <div className="rounded-3xl bg-teal-mist p-5">
          <p className="font-serif text-[17px] leading-snug text-teal-ink">Pause before you act.</p>
          <p className="mt-1.5 text-[13px] leading-relaxed text-teal-ink/75">
            Run any buy, hold or sell idea past Folium first.
          </p>
          <Button asChild size="sm" className="mt-4 w-full">
            <Link to="/app/new">Analyse a decision</Link>
          </Button>
        </div>
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-[#2f2b29]/30" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 flex-col bg-background px-4 py-6 shadow-lift animate-fade-up">
            <div className="flex items-center justify-between px-2">
              <Logo to="/app" />
              <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close menu">
                <X />
              </Button>
            </div>
            <div className="mt-8">
              <NavItems onNavigate={() => setOpen(false)} />
            </div>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-md">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
                <Menu />
              </Button>
              <Logo to="/app" className="md:hidden" />
              <MarketTicker />
            </div>
            <div className="flex items-center gap-1.5">
              <ThemeToggle />
              <UserMenu />
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-8 sm:py-10">
          <React.Suspense
            fallback={
              <div className="space-y-4" role="status" aria-label="Loading page">
                <div className="h-10 w-1/3 animate-soft-pulse rounded-xl bg-surface-2" />
                <div className="h-64 animate-soft-pulse rounded-3xl bg-surface-2" />
              </div>
            }
          >
            <Outlet />
          </React.Suspense>
        </main>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page header                                                         */
/* ------------------------------------------------------------------ */

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="space-y-1.5">
        {eyebrow && <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-primary">{eyebrow}</p>}
        <h1 className="text-3xl leading-tight sm:text-[2.1rem]">{title}</h1>
        {description && <p className="max-w-2xl text-[15px] leading-relaxed text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </div>
  );
}
