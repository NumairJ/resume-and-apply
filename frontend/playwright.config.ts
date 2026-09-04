import { defineConfig, devices } from "@playwright/test";

/**
 * One end-to-end test, run on demand — never as part of `npm test`.
 *
 * It drives the real stack, which means a real Anthropic API call: roughly two cents
 * and up to a minute per run. That is deliberate. Mocking the model here would leave
 * browser → proxy → FastAPI → guardrails → WeasyPrint → volume → download covered by
 * nothing, which is the only integration this test exists to protect.
 *
 * The app must already be running (`docker compose up -d`). There is no `webServer`
 * block because the stack is three Docker services, not a process Playwright can own.
 */
export default defineConfig({
  testDir: "./e2e",
  // Generation alone can take a minute, and the guardrail chain may retry twice inside
  // one request before it answers.
  timeout: 5 * 60_000,
  expect: { timeout: 15_000 },
  // A flake here costs real money, so retries are opt-in rather than automatic.
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
