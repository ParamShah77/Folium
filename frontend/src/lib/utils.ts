import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const fullINR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

/** ₹4.12 Cr · ₹3.85 L · ₹82,450 — how Indian investors read money. */
export function formatINR(amount: number | null | undefined, opts: { compact?: boolean } = {}) {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return "—";
  const compact = opts.compact ?? true;
  const sign = amount < 0 ? "-" : "";
  const a = Math.abs(amount);
  if (compact && a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)} Cr`;
  if (compact && a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2)} L`;
  return `${sign}${fullINR.format(a)}`;
}

/** 2-decimal rupee price for share prices. */
export function formatPrice(amount: number | null | undefined) {
  if (amount === null || amount === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/** Fraction -> signed percent: -0.1832 -> "-18.3%". */
export function formatPct(fraction: number | null | undefined, digits = 1, signed = true) {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return "—";
  const v = fraction * 100;
  const s = v.toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s}%`;
}

export function formatDate(iso: string | null | undefined, withTime = false) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
  });
}

export function relativeTime(iso: string | null | undefined) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
  return formatDate(iso);
}

export function initials(name: string | undefined) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
