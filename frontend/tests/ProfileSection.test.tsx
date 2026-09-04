import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { BulletEditor } from "@/components/BulletEditor";
import { ProfileSection } from "@/components/ProfileSection";
import { skills as skillsApi } from "@/lib/api";
import { profile, recorded } from "./msw/handlers";
import { render } from "./render";
import { Field, Input } from "@/components/ui";
import type { Skill, SkillCreate, SkillUpdate } from "@/types/api";

function SkillsSection({ items = profile.skills }: { items?: Skill[] }) {
  return (
    <ProfileSection<Skill, SkillCreate, SkillUpdate>
      title="Skills"
      items={items}
      collection={skillsApi}
      addLabel="Add skill"
      blank={() => ({ name: "", category: null, position: items.length })}
      view={(item) => <p>{item.name}</p>}
      form={(draft, set) => (
        <Field label="Skill">
          <Input value={draft.name} onChange={(e) => set({ name: e.target.value })} />
        </Field>
      )}
    />
  );
}

beforeEach(() => {
  recorded.length = 0;
});

describe("ProfileSection", () => {
  it("adds an item", async () => {
    const user = userEvent.setup();
    render(<SkillsSection />);

    await user.click(screen.getByRole("button", { name: /add skill/i }));
    await user.type(screen.getByLabelText(/skill/i), "Go");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0]).toMatchObject({
      method: "POST",
      path: "/api/profile/skills",
      body: { name: "Go", position: 2 },
    });
  });

  it("edits an existing item without sending its id in the body", async () => {
    const user = userEvent.setup();
    render(<SkillsSection />);

    await user.click(within(screen.getAllByRole("listitem")[0]).getByText("Edit"));
    await user.clear(screen.getByLabelText(/skill/i));
    await user.type(screen.getByLabelText(/skill/i), "Rust");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0].path).toBe("/api/profile/skills/s-1");
    expect(recorded[0].body).toMatchObject({ name: "Rust" });
    // The id identifies the row in the URL; sending it in the body too would invite
    // the server to try to change a primary key.
    expect(recorded[0].body).not.toHaveProperty("id");
  });

  it("does not write anything when an edit is cancelled", async () => {
    const user = userEvent.setup();
    render(<SkillsSection />);

    await user.click(within(screen.getAllByRole("listitem")[0]).getByText("Edit"));
    await user.type(screen.getByLabelText(/skill/i), "typo");
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(recorded).toHaveLength(0);
    expect(screen.getByText("Python")).toBeVisible();
  });

  it("reorders by sending the whole new order", async () => {
    const user = userEvent.setup();
    render(<SkillsSection />);

    // Move the second item up; the endpoint takes every id in the desired order.
    await user.click(
      within(screen.getAllByRole("listitem")[1]).getByRole("button", {
        name: /move up/i,
      }),
    );

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0]).toMatchObject({
      method: "PUT",
      path: "/api/profile/skills/order",
      body: { ids: ["s-2", "s-1"] },
    });
  });

  it("disables the move controls at the ends of the list", () => {
    render(<SkillsSection />);
    const rows = screen.getAllByRole("listitem");

    expect(
      within(rows[0]).getByRole("button", { name: /move up/i }),
    ).toBeDisabled();
    expect(
      within(rows.at(-1)!).getByRole("button", { name: /move down/i }),
    ).toBeDisabled();
  });

  it("confirms before removing", async () => {
    const user = userEvent.setup();
    render(<SkillsSection />);

    await user.click(within(screen.getAllByRole("listitem")[0]).getByText("Remove"));
    expect(recorded).toHaveLength(0);

    // Scoped to the dialog: the row action and the confirm button share a label.
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: /^remove$/i }),
    );

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0]).toMatchObject({
      method: "DELETE",
      path: "/api/profile/skills/s-1",
    });
  });
});

describe("ProfileSection, grouped", () => {
  const grouped = [
    { id: "s-1", name: "Python", category: "Languages", position: 0 },
    { id: "s-2", name: "Postgres", category: "Databases", position: 1 },
    { id: "s-3", name: "Go", category: "Languages", position: 2 },
    { id: "s-4", name: "Curiosity", category: null, position: 3 },
  ];

  function Grouped() {
    return (
      <ProfileSection<Skill, SkillCreate, SkillUpdate>
        title="Skills"
        items={grouped}
        collection={skillsApi}
        groupBy={(item) => item.category?.trim() ?? ""}
        blank={() => ({ name: "", category: null, position: grouped.length })}
        view={(item) => <p>{item.name}</p>}
        form={(draft, set) => (
          <Field label="Skill">
            <Input value={draft.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
        )}
      />
    );
  }

  it("buckets rows under their category, uncategorised last", () => {
    render(<Grouped />);

    const headings = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual(["Languages", "Databases", "Uncategorised"]);
  });

  it("puts each row under the right heading", () => {
    render(<Grouped />);
    const lists = screen.getAllByRole("list");

    expect(within(lists[0]).getByText("Python")).toBeVisible();
    expect(within(lists[0]).getByText("Go")).toBeVisible();
    expect(within(lists[1]).getByText("Postgres")).toBeVisible();
  });

  it("will not move a row out of its group", () => {
    // Postgres is the second row overall but the first in Databases. Ungrouped, ↑ would
    // swap it with Python and it would appear to jump into another category.
    render(<Grouped />);
    const databases = screen.getAllByRole("list")[1];

    expect(
      within(databases).getByRole("button", { name: /move up/i }),
    ).toBeDisabled();
    expect(
      within(databases).getByRole("button", { name: /move down/i }),
    ).toBeDisabled();
  });

  it("reorders within a group but still sends the whole global order", async () => {
    const user = userEvent.setup();
    render(<Grouped />);
    const languages = screen.getAllByRole("list")[0];

    // Move Go above Python inside Languages.
    await user.click(
      within(languages).getAllByRole("button", { name: /move up/i })[1],
    );

    await waitFor(() => expect(recorded).toHaveLength(1));
    // Every id, because the endpoint rewrites every position — and the other groups
    // keep their relative order.
    expect(recorded[0].body).toEqual({ ids: ["s-3", "s-1", "s-2", "s-4"] });
  });
});

describe("BulletEditor", () => {
  it("reorders bullets within their own experience", async () => {
    const user = userEvent.setup();
    render(<BulletEditor experience={profile.experiences[0]} />);

    await user.click(screen.getAllByRole("button", { name: /move bullet up/i })[1]);

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0]).toMatchObject({
      method: "PUT",
      path: "/api/profile/experiences/exp-1/bullets/order",
      body: { ids: ["b-2", "b-1"] },
    });
  });

  it("shows every bullet of the experience", () => {
    render(<BulletEditor experience={profile.experiences[0]} />);

    expect(screen.getByText(/hardened the payment retry path/i)).toBeVisible();
    expect(screen.getByText(/migrated billing to postgres/i)).toBeVisible();
  });
});
