import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { LogoMark } from "@/components/brand";
import { AppShell, AuthLayout, PublicLayout } from "@/components/layouts";
import { useAuth } from "@/providers/auth";
import Landing from "@/pages/Landing";
import Privacy from "@/pages/Privacy";
import Login from "@/pages/auth/Login";
import Register from "@/pages/auth/Register";
import CheckEmail from "@/pages/auth/CheckEmail";
import VerifyEmail from "@/pages/auth/VerifyEmail";
import ForgotPassword from "@/pages/auth/ForgotPassword";
import ResetPassword from "@/pages/auth/ResetPassword";
import DevMailbox from "@/pages/auth/DevMailbox";
import GoogleReturn from "@/pages/auth/GoogleReturn";
import NotFound from "@/pages/NotFound";
// Signed-in pages carry the charting and form libraries; load them on demand
// so the landing and sign-in pages stay light.
const Dashboard = lazy(() => import("@/pages/app/Dashboard"));
const NewDecision = lazy(() => import("@/pages/app/NewDecision"));
const PortfolioPage = lazy(() => import("@/pages/app/Portfolio"));
const DecisionPage = lazy(() => import("@/pages/app/DecisionPage"));
const HistoryPage = lazy(() => import("@/pages/app/History"));
const SettingsPage = lazy(() => import("@/pages/app/Settings"));
const WelcomePage = lazy(() => import("@/pages/app/Welcome"));

function FullPageLoader() {
  return (
    <div className="flex min-h-dvh items-center justify-center" role="status" aria-label="Loading">
      <LogoMark className="size-11 animate-soft-pulse" />
    </div>
  );
}

/** Pages an account without a Tier 1 profile may still open. */
const OPEN_WITHOUT_PROFILE = ["/app/welcome", "/app/settings"];

/** Signed-in only. Remembers where the user was going. */
function RequireAuth() {
  const { user, loading, signedOutOnPurpose } = useAuth();
  const location = useLocation();
  if (loading) return <FullPageLoader />;
  // Logging out goes home; an expired or missing session goes to sign-in.
  if (!user && signedOutOnPurpose) return <Navigate to="/" replace />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  // A Google sign-up skips the sign-up form, so Tier 1 is asked for first.
  if (user.needs_profile && !OPEN_WITHOUT_PROFILE.includes(location.pathname)) {
    return <Navigate to="/app/welcome" replace state={{ from: location.pathname + location.search }} />;
  }
  return (
    <Suspense fallback={<FullPageLoader />}>
      <Outlet />
    </Suspense>
  );
}

/** Signed-out only (login, register): a signed-in user goes to the app. */
function GuestOnly() {
  const { user, loading } = useAuth();
  if (loading) return <FullPageLoader />;
  if (user) return <Navigate to="/app" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="/privacy" element={<Privacy />} />
      </Route>

      <Route element={<AuthLayout />}>
        <Route element={<GuestOnly />}>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
        </Route>
        <Route path="/check-email" element={<CheckEmail />} />
        <Route path="/auth/verify-email" element={<VerifyEmail />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/dev/mailbox" element={<DevMailbox />} />
        <Route path="/auth/google" element={<GoogleReturn />} />
      </Route>

      <Route element={<RequireAuth />}>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="new" element={<NewDecision />} />
          <Route path="decisions/:id" element={<DecisionPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="welcome" element={<WelcomePage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
