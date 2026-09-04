import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirrors the `@/*` alias in tsconfig.json, which Vitest does not read.
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    // The date formatting is timezone-sensitive by nature — a bare YYYY-MM-DD parsed
    // as UTC renders as the previous day west of Greenwich. Pinning a negative-offset
    // zone means those tests actually exercise the case that broke, rather than
    // passing everywhere the CI happens to run in UTC.
    env: { TZ: "America/Toronto" },
  },
});
