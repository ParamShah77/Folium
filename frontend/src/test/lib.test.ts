import { describe, expect, it } from "vitest";
import { formatINR, formatPct, initials } from "@/lib/utils";
import { confidenceLevel, isProfileComplete, riskFromQuiz, riskLabel } from "@/lib/domain";
import { validateProfile, profilePayload, EMPTY_PROFILE } from "@/components/profile-fields";
import { passwordScore } from "@/pages/auth/shared";

describe("formatINR", () => {
  it("uses lakh and crore like Indian investors read them", () => {
    expect(formatINR(82450)).toBe("₹82,450");
    expect(formatINR(385000)).toBe("₹3.85 L");
    expect(formatINR(41200000)).toBe("₹4.12 Cr");
    expect(formatINR(-150000)).toBe("-₹1.50 L");
  });
  it("can show the full amount", () => {
    expect(formatINR(385000, { compact: false })).toBe("₹3,85,000");
  });
  it("shows a dash for missing values", () => {
    expect(formatINR(null)).toBe("—");
    expect(formatINR(undefined)).toBe("—");
  });
});

describe("formatPct", () => {
  it("turns a fraction into a signed percent", () => {
    expect(formatPct(-0.1832)).toBe("-18.3%");
    expect(formatPct(0.05)).toBe("+5.0%");
    expect(formatPct(0.5, 0, false)).toBe("50%");
  });
});

describe("initials", () => {
  it("takes first and last initials", () => {
    expect(initials("Ananya Iyer")).toBe("AI");
    expect(initials("Meera")).toBe("M");
  });
});

describe("investor profile", () => {
  it("flags missing and out-of-range fields", () => {
    const errs = validateProfile({ ...EMPTY_PROFILE, age: "15" });
    expect(errs.age).toMatch(/between 18 and 100/);
    expect(errs.monthly_income).toBeDefined();
  });
  it("requires the risk quiz at sign-up", () => {
    const v = { ...EMPTY_PROFILE, age: "34", monthly_income: "160000" };
    expect(validateProfile(v, { requireQuiz: true }).risk_answers).toBeDefined();
    expect(validateProfile(v)).toEqual({});
  });
  it("builds the payload with fixed payments defaulting to zero", () => {
    const v = { ...EMPTY_PROFILE, age: "34", monthly_income: "160000", rent_paid: "25000", risk_tolerance: 0.55 };
    expect(profilePayload(v)).toMatchObject({
      age: 34, monthly_income: 160000, monthly_emi: 0, rent_paid: 25000, education_monthly: 0,
      education_end_year: null, risk_tolerance: 0.55,
    });
  });
  it("scores the risk quiz from 0 to 1", () => {
    expect(riskFromQuiz({ drop: 0, goal: 0, experience: 0, need: 0, swing: 0 })).toBe(0);
    expect(riskFromQuiz({ drop: 3, goal: 3, experience: 3, need: 3, swing: 3 })).toBe(1);
    expect(riskFromQuiz({ drop: 1 })).toBeNull();
  });
  it("words confidence instead of showing a percentage", () => {
    expect(confidenceLevel(0.9).label).toBe("High confidence");
    expect(confidenceLevel(0.7).label).toBe("Medium confidence");
    expect(confidenceLevel(0.5).label).toBe("Low confidence");
  });
  it("knows when a stored profile is complete", () => {
    expect(isProfileComplete({ age: 30, risk_tolerance: 0.5, investment_horizon: 10, monthly_income: 1 })).toBe(true);
    expect(isProfileComplete({ age: null, risk_tolerance: 0.5, investment_horizon: 10, monthly_income: 1 })).toBe(false);
  });
  it("labels risk tolerance", () => {
    expect(riskLabel(0.1)).toBe("Cautious");
    expect(riskLabel(0.5)).toBe("Moderate");
    expect(riskLabel(0.9)).toBe("Adventurous");
  });
});

describe("password meter", () => {
  it("rates longer, more varied passwords higher", () => {
    expect(passwordScore("")).toBe(0);
    expect(passwordScore("password")).toBeLessThan(passwordScore("Quiet-Harbour-Lantern-58"));
    expect(passwordScore("Quiet-Harbour-Lantern-58")).toBe(4);
  });
});
