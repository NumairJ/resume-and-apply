import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { SkillsBulkAdd } from "@/components/SkillsBulkAdd";
import { profile, recorded } from "./msw/handlers";
import { render } from "./render";

beforeEach(() => {
  recorded.length = 0;
});

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  render(<SkillsBulkAdd skills={profile.skills} />);
  await user.click(screen.getByRole("button", { name: /paste a list/i }));
}

describe("SkillsBulkAdd", () => {
  it("creates one skill per pasted name, sharing the batch's category", async () => {
    const user = userEvent.setup();
    await openPanel(user);

    await user.type(screen.getByLabelText(/^skills$/i), "Go, Rust, Zig");
    await user.type(screen.getByLabelText(/category/i), "Languages");
    await user.click(screen.getByRole("button", { name: /add 3/i }));

    await waitFor(() => expect(recorded).toHaveLength(3));
    expect(recorded.map((call) => call.body)).toEqual([
      // Positions continue from the two skills already in the fixture profile, so a
      // batch lands after what is already there rather than colliding with it.
      { name: "Go", category: "Languages", position: 2 },
      { name: "Rust", category: "Languages", position: 3 },
      { name: "Zig", category: "Languages", position: 4 },
    ]);
    expect(recorded.every((call) => call.path === "/api/profile/skills")).toBe(true);
  });

  it("skips names already in the profile and says how many", async () => {
    const user = userEvent.setup();
    await openPanel(user);

    // The fixture profile already has Python and Postgres.
    await user.type(screen.getByLabelText(/^skills$/i), "python, Go, POSTGRES");

    expect(
      screen.getByText(/1 to add, 2 already in your profile/i),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: /add 1/i }));

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0].body).toMatchObject({ name: "Go" });
  });

  it("sends no category when none was given", async () => {
    const user = userEvent.setup();
    await openPanel(user);

    await user.type(screen.getByLabelText(/^skills$/i), "Go");
    await user.click(screen.getByRole("button", { name: /add 1/i }));

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0].body).toMatchObject({ name: "Go", category: null });
  });

  it("cannot be submitted with nothing new to add", async () => {
    const user = userEvent.setup();
    await openPanel(user);

    expect(screen.getByRole("button", { name: /add 0/i })).toBeDisabled();

    await user.type(screen.getByLabelText(/^skills$/i), "Python");
    expect(screen.getByRole("button", { name: /add 0/i })).toBeDisabled();
    expect(recorded).toHaveLength(0);
  });

  it("counts what will be created before anything is sent", async () => {
    const user = userEvent.setup();
    await openPanel(user);

    await user.type(screen.getByLabelText(/^skills$/i), "Go\nRust");

    // The count is the only confirmation that the separators were read as intended.
    expect(screen.getByRole("button", { name: /add 2/i })).toBeEnabled();
    expect(recorded).toHaveLength(0);
  });
});
