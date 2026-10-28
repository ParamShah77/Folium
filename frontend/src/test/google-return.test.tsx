import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/providers/auth";
import GoogleReturn, { parseGoogleOutcome } from "@/pages/auth/GoogleReturn";
import { googleLoginHref } from "@/pages/auth/shared";

function renderAt(hash: string) {
  window.history.replaceState(null, "", `/auth/google${hash}`);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/auth/google"]}>
        <AuthProvider>
          <GoogleReturn />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => window.history.replaceState(null, "", "/"));

describe("parseGoogleOutcome", () => {
  it("reads each outcome the server sends", () => {
    expect(parseGoogleOutcome("#result=ok&new=1&next=%2Fapp%2Fportfolio")).toEqual({
      result: "ok",
      isNew: true,
      next: "/app/portfolio",
    });
    expect(parseGoogleOutcome("#result=mfa&token=abc&remember=1")).toEqual({
      result: "mfa",
      token: "abc",
      remember: true,
      next: "/app",
    });
    expect(parseGoogleOutcome("#result=error&code=OAUTH_CANCELLED")).toEqual({
      result: "error",
      code: "OAUTH_CANCELLED",
    });
  });

  it("rejects anything incomplete or unknown", () => {
    expect(parseGoogleOutcome("")).toBeNull();
    expect(parseGoogleOutcome("#result=mfa")).toBeNull();
    expect(parseGoogleOutcome("#result=whatever")).toBeNull();
  });

  it("never sends the browser off the app", () => {
    for (const bad of ["https://evil.example", "//evil.example", "/\\evil.example"]) {
      const out = parseGoogleOutcome(`#result=ok&next=${encodeURIComponent(bad)}`);
      expect(out).toMatchObject({ next: "/app" });
    }
  });
});

describe("googleLoginHref", () => {
  it("carries 'keep me signed in' and the destination to the server", () => {
    expect(googleLoginHref()).toBe("/v1/auth/google/login");
    expect(googleLoginHref({ remember: true, next: "/app/history" })).toBe(
      "/v1/auth/google/login?remember=true&next=%2Fapp%2Fhistory",
    );
  });
});

describe("GoogleReturn", () => {
  it("explains a cancelled sign-in and offers to try again", async () => {
    renderAt("#result=error&code=OAUTH_CANCELLED");
    expect(await screen.findByText(/sign-in was cancelled/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /continue with google/i })).toBeInTheDocument();
    // The fragment is cleared from the address bar once read.
    expect(window.location.hash).toBe("");
  });

  it("offers to keep an account scheduled for deletion", async () => {
    renderAt("#result=deleted&token=tok-123&purge=2026-11-08T00%3A00%3A00%2B00%3A00");
    expect(await screen.findByText(/scheduled for deletion/i)).toBeInTheDocument();
    expect(screen.getByText(/8 November 2026/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep my account" })).toBeInTheDocument();
  });

  it("asks for the two-step code when the account has it on", async () => {
    renderAt("#result=mfa&token=tok-456");
    expect(await screen.findByText("Two-step verification")).toBeInTheDocument();
  });
});

describe("Welcome (Tier 1 after a Google sign-up)", () => {
  it("asks for the investor profile the sign-up form would have", async () => {
    const { default: Welcome } = await import("@/pages/app/Welcome");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    qc.setQueryData(["me"], {
      id: "u1",
      name: "Ananya Iyer",
      email: "a@example.com",
      role: "user",
      mfa_enabled: false,
      has_password: false,
      needs_profile: true,
    });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/app/welcome"]}>
          <AuthProvider>
            <Welcome />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/About you as an investor, Ananya/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save and continue" })).toBeInTheDocument();
  });
});
