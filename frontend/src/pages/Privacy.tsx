import { Link } from "react-router-dom";
import { EyeOff, KeyRound, Lock, Server, ShieldCheck, Trash2 } from "lucide-react";

const SECTIONS: { icon: typeof Lock; title: string; body: React.ReactNode }[] = [
  {
    icon: Server,
    title: "What we collect",
    body: (
      <>
        <p>
          Your name and email; the financial profile you enter (age, income, fixed monthly payments, emergency fund,
          comfort with risk, horizon and goal); your portfolio (holdings, gold, fixed deposits, savings, property,
          loans and rent received); and the decisions you choose to analyse, with their results.
        </p>
        <p>We don't ask for bank, card or broker logins, and we don't read your accounts.</p>
      </>
    ),
  },
  {
    icon: ShieldCheck,
    title: "Why we use it",
    body: (
      <p>
        Only to produce your analyses: to spot behavioural patterns, project what each choice means for your wealth,
        and explain the result. Your data is not used for advertising and is never sold or shared for marketing.
      </p>
    ),
  },
  {
    icon: EyeOff,
    title: "Who can see it",
    body: (
      <p>
        Only you. Your portfolio, financial profile and analyses are isolated at the database level, so one account
        can't read another's data, even through a fault in the application. Changing your email, income or fixed
        payments asks for your password again.
      </p>
    ),
  },
  {
    icon: KeyRound,
    title: "How your account is protected",
    body: (
      <p>
        Passwords are stored only as salted hashes. Two-step verification secrets are encrypted. Sessions use secure,
        HTTP-only cookies with protection against cross-site requests. If you don't tick "Keep me signed in", your
        session ends when you close the browser. When Folium is deployed online, all traffic is served over HTTPS.
      </p>
    ),
  },
  {
    icon: Lock,
    title: "Services we rely on",
    body: (
      <p>
        To value your portfolio we look up public prices: stock and gold prices from Yahoo Finance, and fund prices
        from MFAPI.in. Only the ticker or fund code is sent, never anything about you. If an email service is
        configured, it's used to send verification and password-reset emails. If you sign in with Google, Google
        confirms your identity. If you turn on AI help (Settings, Your data), the comment you write with an analysis
        and that analysis's numbers, but not your name or email, are sent to Google's Gemini to read the comment and
        word the two sides. It's off unless you turn it on.
      </p>
    ),
  },
  {
    icon: Trash2,
    title: "Your choices",
    body: (
      <p>
        You can view and edit your profile and portfolio at any time, and remove any holding. Under Settings, Your data,
        you can download everything Folium holds about you, or delete your account. Deleting signs you out at once and
        gives you 30 days to change your mind by logging in. After that your name, email, profile, portfolio, comments
        and analysis details are erased for good. Completed analyses are sealed in an append-only record so your
        history can't be altered; that record stays, but it can no longer be linked to you.
      </p>
    ),
  },
];

export default function Privacy() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-16 sm:px-8">
      <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-primary">Privacy policy</p>
      <h1 className="mt-3 text-4xl leading-tight">Your data stays yours</h1>
      <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
        Folium helps you make calmer investment decisions. To do that it needs to know about your money, so here is
        exactly what we collect, why, and how we protect it.
      </p>
      <div className="mt-12 space-y-4">
        {SECTIONS.map(({ icon: Icon, title, body }) => (
          <section key={title} className="flex gap-5 rounded-3xl border border-border bg-surface p-6 shadow-soft">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-teal-mist text-primary">
              <Icon className="size-[18px]" />
            </span>
            <div className="space-y-2 text-[15px] leading-relaxed text-muted-foreground">
              <h2 className="font-sans text-base font-medium text-foreground">{title}</h2>
              {body}
            </div>
          </section>
        ))}
      </div>
      <p className="mt-10 text-sm text-subtle-foreground">
        Folium provides information and education, not investment advice.{" "}
        <Link to="/" className="text-primary hover:underline">
          Back to home
        </Link>
      </p>
    </main>
  );
}
