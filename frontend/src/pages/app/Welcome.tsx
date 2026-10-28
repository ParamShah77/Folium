import * as React from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Lock } from "lucide-react";
import { PageHeader } from "@/components/layouts";
import {
  EMPTY_PROFILE,
  ProfileFields,
  profilePayload,
  validateProfile,
  type InvestorProfile,
  type ProfileErrors,
} from "@/components/profile-fields";
import { Button } from "@/components/ui/button";
import { Alert, Card, CardContent } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/providers/auth";

/**
 * Tier 1 for accounts that skipped the sign-up form (Phase C1): signing up
 * with Google creates the account straight away, so the investor profile the
 * sign-up form would have asked for is asked for here, before anything else.
 */
export default function Welcome() {
  const { user, refreshUser } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const next = (location.state as { from?: string } | null)?.from ?? "/app";
  const [profile, setProfile] = React.useState<InvestorProfile>(EMPTY_PROFILE);
  const [errors, setErrors] = React.useState<ProfileErrors>({});
  const [submitError, setSubmitError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);

  if (user && !user.needs_profile) return <Navigate to={next} replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateProfile(profile, { requireQuiz: true });
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setSubmitError(undefined);
    try {
      // First-fill: income and payments may be set here once; changing them
      // later needs the password (Settings → Update securely).
      await api.put("/users/me/profile", { name: user?.name ?? "", ...profilePayload(profile) });
      await qc.invalidateQueries({ queryKey: ["profile"] });
      await refreshUser();
      toast.success("Profile saved");
      navigate(next, { replace: true });
    } catch (err) {
      setSubmitError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        eyebrow="One last step"
        title={`About you as an investor${user ? `, ${user.name.split(" ")[0]}` : ""}`}
        description="Your analyses and projections are personalised with these. You can change them any time."
      />
      <Card>
        <CardContent>
          <form onSubmit={submit} className="space-y-7" noValidate>
            {submitError && <Alert tone="danger">{submitError}</Alert>}
            <ProfileFields value={profile} onChange={setProfile} errors={errors} riskMode="quiz" />
            <Button type="submit" size="lg" className="w-full" loading={busy}>
              Save and continue
            </Button>
            <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
              <Lock className="mt-0.5 size-3.5 shrink-0 text-primary" />
              Your data is isolated to your account and never sold or shared.
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
