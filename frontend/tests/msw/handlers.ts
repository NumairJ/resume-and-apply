import { http, HttpResponse } from "msw";

import type { Application, Profile, Provider } from "@/types/api";

/**
 * The backend, as far as these tests are concerned.
 *
 * Requests are relative (`/api/...`), and jsdom resolves them against localhost, so
 * these patterns match the same paths the real client builds.
 */

export const provider: Provider = {
  name: "anthropic",
  available_models: ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5"],
};

export const profile: Profile = {
  id: "user-1",
  full_name: "Dana Reed",
  email: "dana@example.com",
  phone: null,
  location: "Toronto",
  summary: null,
  education: [],
  experiences: [
    {
      id: "exp-1",
      company: "Northwind Systems",
      title: "Software Engineer",
      location: null,
      start_date: "2021-03-01",
      end_date: "2024-06-01",
      position: 0,
      bullets: [
        { id: "b-1", text: "Hardened the payment retry path", position: 0 },
        { id: "b-2", text: "Migrated billing to Postgres", position: 1 },
      ],
    },
  ],
  skills: [
    { id: "s-1", name: "Python", category: "Languages", position: 0 },
    { id: "s-2", name: "Postgres", category: "Databases", position: 1 },
  ],
  projects: [
    {
      id: "proj-1",
      name: "Portfolio Site",
      tech_stack: "Next.js, Postgres",
      url: "https://example.com/portfolio",
      start_date: null,
      end_date: null,
      position: 0,
      bullets: [
        { id: "pb-1", text: "Built a typed API layer", position: 0 },
        { id: "pb-2", text: "Deployed as a single container", position: 1 },
      ],
    },
  ],
  links: [],
};

function application(
  id: string,
  company: string,
  title: string,
  status: Application["status"],
  updated: string,
): Application {
  return {
    id,
    status,
    applied_at: null,
    notes: null,
    created_at: updated,
    updated_at: updated,
    job_posting: {
      id: `job-${id}`,
      company,
      title,
      location: null,
      employment_type: null,
      description: null,
      requirements: null,
      salary_range: null,
      source_url: `https://boards.example.com/${id}`,
      extraction_method: "ats_greenhouse",
      expires_at: null,
      created_at: updated,
    },
    resumes: [],
  };
}

export const applications: Application[] = [
  application("a-1", "Umbrella", "Backend Engineer", "applied", "2026-09-03T10:00:00Z"),
  application("a-2", "Initech", "Platform Engineer", "saved", "2026-09-01T10:00:00Z"),
  application("a-3", "Globex", "Data Engineer", "rejected", "2026-08-20T10:00:00Z"),
];

/** Every mutation a test makes lands here, so assertions can read what was sent. */
export const recorded: { method: string; path: string; body: unknown }[] = [];

async function record(request: Request) {
  const body = await request.json().catch(() => null);
  recorded.push({
    method: request.method,
    path: new URL(request.url).pathname,
    body,
  });
}

export const handlers = [
  http.get("/api/providers", () => HttpResponse.json([provider])),
  http.get("/api/profile", () => HttpResponse.json(profile)),
  http.get("/api/applications", () => HttpResponse.json(applications)),

  http.patch("/api/applications/:id", async ({ request }) => {
    await record(request);
    return HttpResponse.json(applications[0]);
  }),
  http.delete("/api/applications/:id", async ({ request }) => {
    await record(request);
    return new HttpResponse(null, { status: 204 });
  }),

  http.post("/api/profile/skills", async ({ request }) => {
    await record(request);
    return HttpResponse.json(
      { id: "s-new", name: "Go", category: null, position: 2 },
      { status: 201 },
    );
  }),
  http.patch("/api/profile/skills/:id", async ({ request }) => {
    await record(request);
    return HttpResponse.json(profile.skills[0]);
  }),
  http.delete("/api/profile/skills/:id", async ({ request }) => {
    await record(request);
    return new HttpResponse(null, { status: 204 });
  }),
  http.put("/api/profile/skills/order", async ({ request }) => {
    await record(request);
    return HttpResponse.json(profile.skills);
  }),

  http.put("/api/profile/experiences/:id/bullets/order", async ({ request }) => {
    await record(request);
    return HttpResponse.json(profile.experiences[0].bullets);
  }),

  // Projects have their own nested bullet routes now. `onUnhandledRequest: "error"`
  // means every one a test can reach has to be mocked, not just the ones asserted on.
  http.post("/api/profile/projects/:id/bullets", async ({ request }) => {
    await record(request);
    return HttpResponse.json(
      { id: "pb-new", text: "new", position: 2 },
      { status: 201 },
    );
  }),
  http.patch("/api/profile/projects/:id/bullets/:bulletId", async ({ request }) => {
    await record(request);
    return HttpResponse.json(profile.projects[0].bullets[0]);
  }),
  http.delete("/api/profile/projects/:id/bullets/:bulletId", async ({ request }) => {
    await record(request);
    return new HttpResponse(null, { status: 204 });
  }),
  http.put("/api/profile/projects/:id/bullets/order", async ({ request }) => {
    await record(request);
    return HttpResponse.json(profile.projects[0].bullets);
  }),
];
