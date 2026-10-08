import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "@/providers/auth";

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(async () => ({ data: { id: "u1", name: "Ananya Iyer", email: "a@example.com", role: "user", mfa_enabled: false } })),
    post: vi.fn(async () => ({ data: {} })),
  },
}));

function Probe() {
  const { user, loading, logout } = useAuth();
  if (loading) return <p>loading</p>;
  return (
    <div>
      <p>{user ? `signed in as ${user.name}` : "signed out"}</p>
      <button onClick={() => logout()}>Log out</button>
    </div>
  );
}

describe("AuthProvider", () => {
  it("shows the user as signed out immediately after logout", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("signed in as Ananya Iyer")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    // Regression: clearing the whole cache first left the old user on screen
    // ("Open dashboard" after logout) until a full page reload.
    await waitFor(() => expect(screen.getByText("signed out")).toBeInTheDocument());
  });
});
