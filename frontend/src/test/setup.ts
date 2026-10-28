import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; Radix's slider (the profile form) measures itself with one.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
