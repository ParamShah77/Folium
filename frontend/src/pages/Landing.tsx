import { Link } from "react-router-dom";
import {
  ArrowRight,
  BrainCircuit,
  EyeOff,
  FileText,
  KeyRound,
  Languages,
  LineChart,
  Lock,
  MessageSquareText,
  PieChart,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { BIAS_META, BIAS_ORDER } from "@/lib/domain";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth";

function HeroPreview() {
  return (
    <div className="relative">
      <div className="absolute -inset-6 -z-10 rounded-[2.5rem] bg-blush/60 blur-2xl dark:bg-blush/40" aria-hidden />
      <div className="rounded-[2rem] border border-border bg-surface p-6 shadow-lift">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Example analysis</p>
            <p className="mt-1 font-serif text-xl">HDFCBANK · sell</p>
            <p className="text-sm text-muted-foreground">Down 18.4% · 9% of your portfolio</p>
          </div>
          <span className="shrink-0 whitespace-nowrap rounded-full bg-orange-mist px-3 py-1 text-xs font-medium text-orange-ink">
            Loss aversion
          </span>
        </div>

        <svg viewBox="0 0 320 130" className="mt-6 w-full" aria-label="Projection to your time horizon: holding grows faster than selling">
          <path d="M0 110 C80 100 160 70 320 18 L320 64 C160 92 80 106 0 112 Z" fill="var(--hold)" opacity="0.18" />
          <path d="M0 111 C80 104 160 84 320 42" fill="none" stroke="var(--hold)" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M0 112 C80 111 160 100 320 78 L320 100 C160 111 80 113 0 113 Z" fill="var(--sell)" opacity="0.2" />
          <path d="M0 112 C80 110 160 104 320 90" fill="none" stroke="var(--sell)" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
        <div className="mt-2 flex justify-between text-xs text-muted-foreground">
          <span>Today</span>
          <span>When you need it</span>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3">
          <div className="rounded-2xl bg-hold-mist px-4 py-3">
            <p className="flex items-center gap-1.5 text-xs text-teal-ink">
              <span className="size-2 rounded-full bg-hold" /> If you hold
            </p>
            <p className="tabular mt-1 font-serif text-xl">₹6.84 L</p>
          </div>
          <div className="rounded-2xl bg-sell-mist px-4 py-3">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="size-2 rounded-full bg-sell" /> If you sell
            </p>
            <p className="tabular mt-1 font-serif text-xl">₹3.12 L</p>
          </div>
        </div>
        <p className="mt-4 rounded-2xl bg-surface-2 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Our read: hold.</span> Staying invested came out ahead in most of
          the futures we simulated for you.
        </p>
      </div>
    </div>
  );
}

const STEPS = [
  {
    icon: Wallet,
    title: "Add your portfolio once",
    body: "Stocks, mutual funds, gold, fixed deposits, property and loans. Prices for shares, funds and gold update on their own.",
  },
  {
    icon: MessageSquareText,
    title: "Pick a holding and your instinct",
    body: "Thinking of selling, holding or buying more? Choose the holding and say what you're tempted to do, and why.",
  },
  {
    icon: LineChart,
    title: "See it against your whole picture",
    body: "Folium names the bias behind the moment and shows what each choice means for your wealth by the time you need it, after tax.",
  },
];

const FEATURES = [
  {
    icon: BrainCircuit,
    title: "Spots the bias",
    body: "Loss aversion, herd behaviour or the disposition effect, named in plain words, with what weighed most in the call.",
  },
  {
    icon: LineChart,
    title: "Shows two futures",
    body: "A thousand possible paths for your money, if you hold and if you sell, for your age, risk comfort and horizon.",
  },
  {
    icon: PieChart,
    title: "Sees the whole portfolio",
    body: "Each decision is weighed against your net worth, monthly surplus and how much of your money is in shares.",
  },
  {
    icon: Languages,
    title: "Explains it simply",
    body: "A short story in English or Hindi that you can download and keep, or share with your adviser.",
  },
];

const PRIVACY = [
  { icon: Lock, title: "Locked down", body: "Passwords are hashed, two-step secrets are encrypted, and sessions use secure, HTTP-only cookies." },
  { icon: EyeOff, title: "Private by design", body: "Every account's data is isolated at the database level. Nobody else's account can see yours." },
  { icon: KeyRound, title: "Two-step verification", body: "Protect your account with a code from an authenticator app, plus backup codes." },
  { icon: UserCheck, title: "Never sold", body: "We don't sell or share your data, and we don't show ads. Your financial picture stays yours." },
  { icon: ShieldCheck, title: "Re-check for big changes", body: "Changing your email, income or payments asks for your password again." },
  { icon: FileText, title: "A record that can't be edited", body: "Every analysis is written to an append-only record that can't be changed or deleted afterwards." },
];

export default function Landing() {
  const { user } = useAuth();
  return (
    <main>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute -left-40 top-10 -z-10 size-[32rem] rounded-full bg-teal-mist blur-3xl" aria-hidden />
        <div className="mx-auto grid max-w-6xl items-center gap-14 px-5 pb-20 pt-12 sm:px-8 lg:grid-cols-[1.05fr_1fr] lg:pb-28 lg:pt-20">
          <div className="animate-fade-up">
            <Badge tone="teal" className="px-3 py-1">
              <Sparkles className="size-3.5" /> Calm, clear decisions for your money
            </Badge>
            <h1 className="mt-6 text-[2.75rem] leading-[1.05] sm:text-6xl">
              Spot the bias <span className="italic text-primary">before</span> you sell.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
              Folium looks at your whole portfolio, names the bias behind the decision you're about to make, and shows
              what it means for your wealth by the time you need the money.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              {user ? (
                <Button asChild size="lg">
                  <Link to="/app">
                    Go to your dashboard <ArrowRight />
                  </Link>
                </Button>
              ) : (
                <>
                  <Button asChild size="lg">
                    <Link to="/register">
                      Create your free account <ArrowRight />
                    </Link>
                  </Button>
                  <Button asChild size="lg" variant="outline">
                    <Link to="/login">Log in</Link>
                  </Button>
                </>
              )}
            </div>
            <p className="mt-6 flex items-center gap-2 text-sm text-subtle-foreground">
              <Lock className="size-3.5" /> Private by design · Made for Indian investors
            </p>
          </div>
          <div className="animate-fade-up [animation-delay:120ms]">
            <HeroPreview />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 border-t border-border bg-surface-2/50">
        <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
          <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-primary">How it works</p>
          <h2 className="mt-3 max-w-xl text-4xl leading-tight">Three quiet steps between an impulse and an action.</h2>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <div key={title} className="rounded-3xl border border-border bg-surface p-7 shadow-soft">
                <div className="flex items-center justify-between">
                  <span className="flex size-11 items-center justify-center rounded-2xl bg-teal-mist text-primary">
                    <Icon className="size-5" />
                  </span>
                  <span className="font-serif text-3xl text-sand">0{i + 1}</span>
                </div>
                <h3 className="mt-6 text-xl">{title}</h3>
                <p className="mt-2 leading-relaxed text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* The four biases */}
      <section className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
        <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-primary">What it looks for</p>
            <h2 className="mt-3 text-4xl leading-tight">Four patterns behind most costly decisions.</h2>
            <p className="mt-4 leading-relaxed text-muted-foreground">
              Each one gets a single colour, everywhere in the app, so you learn to recognise them at a glance.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {BIAS_ORDER.map((b) => (
              <div key={b} className="rounded-3xl border border-border bg-surface p-6">
                <span className={cn("inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium", BIAS_META[b].soft)}>
                  <span className={cn("size-2 rounded-full", BIAS_META[b].dot)} />
                  {BIAS_META[b].label}
                </span>
                <p className="mt-4 leading-relaxed text-muted-foreground">{BIAS_META[b].description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What you get */}
      <section id="features" className="scroll-mt-20 border-t border-border bg-surface-2/50">
        <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
          <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-primary">What you get</p>
          <h2 className="mt-3 max-w-2xl text-4xl leading-tight">Clear answers, in rupees, for your situation.</h2>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-3xl border border-border bg-surface p-6">
                <span className="flex size-10 items-center justify-center rounded-2xl bg-teal-mist text-primary">
                  <Icon className="size-5" />
                </span>
                <h3 className="mt-5 text-lg">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Security and data privacy */}
      <section id="security" className="scroll-mt-20">
        <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
          <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-primary">Security and data privacy</p>
              <h2 className="mt-3 text-4xl leading-tight">Your data stays yours.</h2>
              <p className="mt-4 leading-relaxed text-muted-foreground">
                Your portfolio is some of the most personal information you have. Folium is built to keep it private and
                protected.
              </p>
              <Button asChild variant="link" className="mt-4">
                <Link to="/privacy">
                  Read our privacy policy <ArrowRight />
                </Link>
              </Button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {PRIVACY.map(({ icon: Icon, title, body }) => (
                <div key={title} className="flex gap-4 rounded-3xl border border-border bg-surface p-5">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-blush text-rose">
                    <Icon className="size-[18px]" />
                  </span>
                  <div>
                    <h3 className="font-sans text-[15px] font-medium">{title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      {!user && (
        <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
          <div className="relative overflow-hidden rounded-[2.5rem] bg-teal-mist px-8 py-14 text-center sm:px-16">
            <div className="absolute -right-20 -top-20 size-72 rounded-full bg-blush/70 blur-3xl" aria-hidden />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl text-4xl leading-tight text-teal-ink">
                The next time the market tests your nerve, ask first.
              </h2>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Button asChild size="lg">
                  <Link to="/register">Create your free account</Link>
                </Button>
                <Button asChild size="lg" variant="ghost">
                  <Link to="/login">Log in</Link>
                </Button>
              </div>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
