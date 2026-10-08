import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The API is proxied rather than called cross-origin: auth cookies are
// SameSite=Lax and the backend's CSRF check is double-submit, both of which
// are simplest and safest when the browser sees a single origin.
const API = process.env.FOLIUM_API_URL ?? "http://127.0.0.1:8000";
// 3000 matches FRONTEND_URL in .env (used in email links). PORT overrides it
// when 3000 is taken by something else.
const PORT = Number(process.env.PORT ?? 3000);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  server: {
    port: PORT,
    strictPort: true,
    proxy: {
      "/v1": { target: API, changeOrigin: false },
      "/health": { target: API, changeOrigin: false },
    },
  },
  preview: {
    port: PORT,
    proxy: {
      "/v1": { target: API, changeOrigin: false },
      "/health": { target: API, changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
