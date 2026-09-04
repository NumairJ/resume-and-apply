import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ProviderSwitcher } from "@/components/ProviderSwitcher";
import { PROVIDER_STORAGE_KEY } from "@/lib/providerSettings";
import { render } from "./render";

const KEY = "sk-ant-api03-abcdefghijklmnop9f2a";

async function saveKey(user: ReturnType<typeof userEvent.setup>, key = KEY) {
  await user.click(screen.getByRole("button", { name: /set api key/i }));
  await user.type(screen.getByLabelText(/api key/i), key);
  await user.click(screen.getByRole("button", { name: /^save$/i }));
}

describe("ProviderSwitcher", () => {
  it("persists the key to localStorage", async () => {
    const user = userEvent.setup();
    render(<ProviderSwitcher />);

    await saveKey(user);

    await waitFor(() => {
      const stored = window.localStorage.getItem(PROVIDER_STORAGE_KEY);
      expect(stored).toBeTruthy();
      expect(JSON.parse(stored!).apiKey).toBe(KEY);
    });
  });

  it("masks the key everywhere it is displayed", async () => {
    const user = userEvent.setup();
    render(<ProviderSwitcher />);

    await saveKey(user);

    // The trigger shows the masked form, and the full key appears nowhere on screen.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /sk-ant-…9f2a/ })).toBeVisible(),
    );
    expect(document.body.textContent).not.toContain(KEY);
  });

  it("clears the key", async () => {
    const user = userEvent.setup();
    render(<ProviderSwitcher />);
    await saveKey(user);

    await user.click(screen.getByRole("button", { name: /set api key|sk-ant/i }));
    await user.click(screen.getByRole("button", { name: /clear key/i }));

    await waitFor(() =>
      expect(window.localStorage.getItem(PROVIDER_STORAGE_KEY)).toBeNull(),
    );
    expect(screen.getByRole("button", { name: /set api key/i })).toBeVisible();
  });

  it("offers the models the backend reports rather than a hardcoded list", async () => {
    const user = userEvent.setup();
    render(<ProviderSwitcher />);

    await user.click(screen.getByRole("button", { name: /set api key/i }));

    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "claude-sonnet-5" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("option", { name: "claude-opus-5" })).toBeInTheDocument();
  });

  it("survives a corrupted localStorage entry", async () => {
    // A bad entry must not take the whole navbar down with it.
    window.localStorage.setItem(PROVIDER_STORAGE_KEY, "{not json");
    render(<ProviderSwitcher />);

    expect(screen.getByRole("button", { name: /set api key/i })).toBeVisible();
  });
});
