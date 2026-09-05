import { expect, test, type APIRequestContext } from "@playwright/test";

/**
 * The one end-to-end test: paste a URL, correct the parse, generate, save, change
 * status, download the PDF.
 *
 * **This spends money.** Generation is a real Anthropic call, so this is wired to
 * `npm run test:e2e` and is deliberately not part of `npm test`. Mocking the model
 * would leave the integration it exists to protect — browser through the Next proxy,
 * FastAPI, the guardrail chain, WeasyPrint, the shared volume, and back out as a
 * download — covered by nothing at all.
 *
 * It runs against whatever data is already in the dev database and must not disturb
 * it: everything it creates is recorded and removed afterwards by id, and it never
 * edits the user's personal information.
 */

const BOARD = "stripe";

// Recorded so teardown removes exactly what this test made, and nothing else.
const created: {
  experienceId?: string;
  projectId?: string;
  skillIds: string[];
  /** The row the backend created, captured from the extract response — see below. */
  jobPostingId?: string;
} = { skillIds: [] };

/**
 * A currently-open engineering posting, discovered rather than hardcoded.
 *
 * A pinned job id would 404 the moment the role is filled, and the test would then be
 * reporting Stripe's hiring rather than this application's health.
 */
async function findLivePosting(): Promise<string> {
  const response = await fetch(
    `https://boards-api.greenhouse.io/v1/boards/${BOARD}/jobs?content=false`,
  );
  expect(response.ok, "Greenhouse board API is reachable").toBeTruthy();

  const { jobs } = (await response.json()) as {
    jobs: { id: number; title: string }[];
  };
  // An engineering role, so the seeded profile is a plausible match — a hopeless
  // pairing makes the guardrails reject drafts and turns a green path red for the
  // wrong reason.
  const job =
    jobs.find(
      (candidate) =>
        /engineer/i.test(candidate.title) && !/sales|account/i.test(candidate.title),
    ) ?? jobs[0];

  expect(job, "the board lists at least one job").toBeTruthy();
  return `https://job-boards.greenhouse.io/${BOARD}/jobs/${job.id}`;
}

async function seedProfile(api: APIRequestContext) {
  const experience = await api.post("/api/profile/experiences", {
    data: {
      company: "Northwind Systems",
      title: "Senior Software Engineer",
      location: "Toronto, ON",
      start_date: "2021-03-01",
      end_date: "2024-06-01",
      position: 0,
      bullets: [
        {
          text: "Reduced payment service error rates from 2.1% to 0.3% by rebuilding the retry and idempotency path",
          position: 0,
        },
        {
          text: "Migrated the billing database to Postgres with zero downtime for 40,000 active accounts",
          position: 1,
        },
        {
          text: "Led a three-person team delivering a new invoicing service used by every downstream billing job",
          position: 2,
        },
      ],
    },
  });
  expect(experience.ok(), await experience.text()).toBeTruthy();
  created.experienceId = (await experience.json()).id;

  // A project too, so the run actually exercises the P-label path: the model has to
  // cite `P1` and rewrite this description, and the server has to fill the name, URL and
  // dates from this row. Without one seeded, the model cites no project and the whole
  // Projects section would go untested by the only test that talks to a real model.
  const project = await api.post("/api/profile/projects", {
    data: {
      name: "Ledger Reconciler",
      description:
        "Open-source tool that reconciles double-entry ledgers against bank exports, written in Python with a Postgres store",
      url: "https://github.com/example/ledger-reconciler",
      start_date: "2023-01-01",
      end_date: "2023-08-01",
      position: 0,
    },
  });
  expect(project.ok(), await project.text()).toBeTruthy();
  created.projectId = (await project.json()).id;

  for (const [index, name] of ["Python", "Postgres", "Go"].entries()) {
    const skill = await api.post("/api/profile/skills", {
      data: { name, category: null, position: index },
    });
    expect(skill.ok()).toBeTruthy();
    created.skillIds.push((await skill.json()).id);
  }
}

/** The application this run created, if any — matched on the posting row's id. */
async function trackedApplication(api: APIRequestContext) {
  const listed = await api.get("/api/applications");
  if (!listed.ok()) return undefined;
  const all = (await listed.json()) as {
    id: string;
    status: string;
    resumes: unknown[];
    job_posting: { id: string };
  }[];
  return all.find((entry) => entry.job_posting.id === created.jobPostingId);
}

async function teardown(api: APIRequestContext) {
  // Delete the application first: that cascades its resume rows, unlinks the PDFs from
  // the shared volume, and restores the job posting's TTL so it sweeps itself.
  const application = await trackedApplication(api);
  if (application) await api.delete(`/api/applications/${application.id}`);

  for (const id of created.skillIds) await api.delete(`/api/profile/skills/${id}`);
  if (created.projectId) await api.delete(`/api/profile/projects/${created.projectId}`);
  if (created.experienceId) {
    await api.delete(`/api/profile/experiences/${created.experienceId}`);
  }
}

test.beforeAll(async ({ request }) => {
  const health = await request.get("/api/");
  expect(
    health.ok(),
    "the stack must already be running — try `docker compose up -d`",
  ).toBeTruthy();

  await seedProfile(request);
});

test.afterAll(async ({ request }) => {
  await teardown(request);
});

test("paste a posting, generate a resume, track it, download the PDF", async ({
  page,
  request,
}) => {
  const postingUrl = await findLivePosting();

  // --- paste and extract ----------------------------------------------------
  await page.goto("/apply");
  await page.getByLabel("Job posting URL").fill(postingUrl);

  // Capture the row the backend created rather than matching on the pasted URL later.
  // The Greenhouse adapter stores the employer's *canonical* apply link — Stripe's
  // board mirrors to `stripe.com/jobs/search?gh_jid=…` — so what is stored is not what
  // was typed, and the id is the only thing that reliably identifies the row.
  const extracted = page.waitForResponse((response) =>
    response.url().includes("/api/jobs/extract"),
  );
  await page.getByRole("button", { name: "Read posting" }).click();
  created.jobPostingId = (await (await extracted).json()).job.id;

  const editDetails = page.getByRole("button", { name: "Edit details" });
  await expect(editDetails).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Read from the Greenhouse API")).toBeVisible();

  // --- correct a mis-parsed field before it becomes a resume ----------------
  await editDetails.click();
  const location = page.getByLabel("Location");
  await location.fill("Remote — corrected by the test");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Remote — corrected by the test")).toBeVisible();

  // --- generate -------------------------------------------------------------
  await page.getByRole("button", { name: "Generate resume" }).click();

  // The long one: a real model call, plus up to two guardrail retries inside the
  // single request.
  const preview = page.locator('iframe[title="Resume preview"]');
  await expect(preview).toBeVisible({ timeout: 240_000 });

  // The rationale is the model's account of what it chose, and the Apply page's
  // reason for existing over a plain "download".
  await expect(page.getByText("Why these bullets")).toBeVisible();

  // The preview is the literal document WeasyPrint printed, so the seeded employer
  // has to appear inside the iframe rather than merely on the page around it.
  await expect(
    preview.contentFrame().getByText("Northwind Systems"),
  ).toBeVisible();

  // The seeded project, with its name and URL taken from the profile row rather than
  // written by the model — the whole point of the P-label scheme.
  await expect(
    preview.contentFrame().getByRole("heading", { name: "Ledger Reconciler" }),
  ).toBeVisible();
  await expect(
    preview.contentFrame().getByText("github.com/example/ledger-reconciler"),
  ).toBeVisible();

  await expect(
    preview.contentFrame().getByRole("heading", { name: "Projects" }),
  ).toBeVisible();

  // Not asserted here: that the PDF is one page. The iframe holds the unpaginated HTML,
  // so page count is not observable from the browser — `test_render.py` measures it on
  // the laid-out document instead, which is where it can actually be seen.

  // --- save, by marking it applied -----------------------------------------
  await page.getByRole("button", { name: "Mark as applied" }).click();
  await expect(page.getByText("Marked as applied")).toBeVisible();

  // --- it is tracked, and the status is editable ---------------------------
  await page.goto("/applications");
  const row = page.getByRole("row").filter({ hasText: "Stripe" }).first();
  await expect(row).toBeVisible();

  const status = row.getByLabel(/^Status for/);
  await expect(status).toHaveValue("applied");
  await status.selectOption("interviewing");
  await expect(page.getByText("Application updated")).toBeVisible();

  // --- download the PDF ----------------------------------------------------
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    row.getByRole("link", { name: "PDF" }).click(),
  ]);

  expect(download.suggestedFilename()).toBe("resume-stripe.pdf");
  const path = await download.path();
  const { readFile } = await import("node:fs/promises");
  const bytes = await readFile(path);
  expect(
    bytes.subarray(0, 5).toString(),
    "the download is a real PDF, not an error page",
  ).toBe("%PDF-");

  // --- and the status change actually persisted ----------------------------
  const tracked = await trackedApplication(request);
  expect(tracked, "the application is tracked against the extracted posting").toBeTruthy();
  expect(tracked!.status).toBe("interviewing");
  expect(tracked!.resumes).toHaveLength(1);
});
