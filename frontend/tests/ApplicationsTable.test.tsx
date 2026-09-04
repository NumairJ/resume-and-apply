import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { ApplicationsTable } from "@/components/ApplicationsTable";
import { applications, recorded } from "./msw/handlers";
import { render } from "./render";

/** Company names in row order, ignoring the header row. */
function companies(): string[] {
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[0].textContent ?? "");
}

beforeEach(() => {
  recorded.length = 0;
});

describe("ApplicationsTable", () => {
  it("shows every application by default", () => {
    render(<ApplicationsTable rows={applications} />);

    expect(screen.getByText("Umbrella")).toBeVisible();
    expect(screen.getByText("Initech")).toBeVisible();
    expect(screen.getByText("3 of 3")).toBeVisible();
  });

  it("filters by company or role", async () => {
    const user = userEvent.setup();
    render(<ApplicationsTable rows={applications} />);

    await user.type(screen.getByLabelText(/filter by company or role/i), "plat");

    // Matches the *role* "Platform Engineer", not just the company.
    expect(screen.getByText("Initech")).toBeVisible();
    expect(screen.queryByText("Umbrella")).not.toBeInTheDocument();
    expect(screen.getByText("1 of 3")).toBeVisible();
  });

  it("filters by status", async () => {
    const user = userEvent.setup();
    render(<ApplicationsTable rows={applications} />);

    await user.selectOptions(screen.getByLabelText(/filter by status/i), "rejected");

    expect(screen.getByText("Globex")).toBeVisible();
    expect(screen.queryByText("Umbrella")).not.toBeInTheDocument();
  });

  it("sorts by company, and reverses on a second click", async () => {
    const user = userEvent.setup();
    render(<ApplicationsTable rows={applications} />);

    const header = screen.getByRole("button", { name: /company \/ role/i });

    await user.click(header);
    expect(companies()[0]).toContain("Globex");

    await user.click(header);
    expect(companies()[0]).toContain("Umbrella");
  });

  it("defaults to newest first", () => {
    render(<ApplicationsTable rows={applications} />);
    expect(companies()[0]).toContain("Umbrella");
  });

  it("sends a status change to the backend", async () => {
    const user = userEvent.setup();
    render(<ApplicationsTable rows={applications} />);

    await user.selectOptions(
      screen.getByLabelText(/status for umbrella/i),
      "interviewing",
    );

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0]).toMatchObject({
      method: "PATCH",
      path: "/api/applications/a-1",
      body: { status: "interviewing" },
    });
  });

  it("confirms before deleting, and does nothing if cancelled", async () => {
    const user = userEvent.setup();
    render(<ApplicationsTable rows={applications} />);

    await user.click(
      screen.getByRole("button", { name: /delete application for umbrella/i }),
    );
    // Scoped to the dialog: the row action and the confirm button share a label, which
    // is correct in the UI but ambiguous to a global query.
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: /cancel/i }),
    );

    expect(recorded).toHaveLength(0);
  });

  it("deletes once confirmed", async () => {
    const user = userEvent.setup();
    render(<ApplicationsTable rows={applications} />);

    await user.click(
      screen.getByRole("button", { name: /delete application for umbrella/i }),
    );
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: /^delete$/i }),
    );

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0]).toMatchObject({
      method: "DELETE",
      path: "/api/applications/a-1",
    });
  });

  it("keeps existing notes when the modal is saved untouched", async () => {
    // Regression: the draft started empty rather than from the saved notes, so opening
    // the modal and pressing Save wiped whatever was already there.
    const user = userEvent.setup();
    const withNotes = [{ ...applications[0], notes: "Referred by Sam" }];
    render(<ApplicationsTable rows={withNotes} />);

    await user.click(screen.getByRole("button", { name: /notes for umbrella/i }));
    await user.click(screen.getByRole("button", { name: /save notes/i }));

    await waitFor(() => expect(recorded).toHaveLength(1));
    expect(recorded[0].body).toMatchObject({ notes: "Referred by Sam" });
  });

  it("says so when a filter matches nothing", async () => {
    const user = userEvent.setup();
    render(<ApplicationsTable rows={applications} />);

    await user.type(screen.getByLabelText(/filter by company or role/i), "zzzz");

    expect(screen.getByText(/no applications match/i)).toBeVisible();
  });
});
