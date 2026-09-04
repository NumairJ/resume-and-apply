/**
 * The one typed client. Every backend call goes through here.
 *
 * **Relative paths only.** The browser never learns the backend's origin — it talks to
 * `localhost:3000/api/...` and the Next rewrite makes the hop to FastAPI server-side.
 * That is the whole architecture (see CLAUDE.md), and hardcoding a backend URL anywhere
 * in the app would quietly break it in Docker while still working locally.
 *
 * The rewrite strips `/api`, so `/api/profile` here arrives at the backend as `/profile`.
 */

import type {
  Application,
  ApplicationCreate,
  ApplicationUpdate,
  Education,
  EducationCreate,
  EducationUpdate,
  ErrorDetail,
  Experience,
  ExperienceBullet,
  ExperienceBulletCreate,
  ExperienceBulletUpdate,
  ExperienceCreate,
  ExperienceUpdate,
  ExtractionResponse,
  GenerateResumeResponse,
  Health,
  JobPosting,
  JobPostingUpdate,
  Link,
  LinkCreate,
  LinkUpdate,
  Profile,
  Project,
  ProjectCreate,
  ProjectUpdate,
  Provider,
  Skill,
  SkillCreate,
  SkillUpdate,
  User,
  UserUpdate,
} from "@/types/api";
// The provider switcher's settings live in their own module because two unrelated
// places need them: it writes, and `request()` below reads on every call.
import { providerHeaders } from "@/lib/providerSettings";

const BASE = "/api";

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

/**
 * A failed request, carrying the backend's own error shape.
 *
 * `detail` is deliberately kept as the union rather than flattened to a string: a
 * guardrail rejection sends `{message, violations}` and a non-posting page sends
 * `{message, reasons}`, and those lists are the most useful thing the UI can show.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: ErrorDetail,
  ) {
    super(typeof detail === "string" ? detail : detail.message);
    this.name = "ApiError";
  }

  /** The specific reasons behind a 422, if the backend supplied any. */
  get reasons(): string[] {
    if (typeof this.detail === "string") return [];
    return this.detail.violations ?? this.detail.reasons ?? [];
  }
}

async function readDetail(response: Response): Promise<ErrorDetail> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      return (body as { detail: ErrorDetail }).detail;
    }
  } catch {
    // Not JSON. A proxy that gave up mid-request produces exactly this, and it is not
    // a backend error shape — fall through to a status-based message.
  }
  return `Request failed with status ${response.status}`;
}

async function request<T>(
  path: string,
  method: Method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...providerHeaders(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }

  // 204 carries no body at all, and calling .json() on it throws.
  const payload: unknown =
    response.status === 204 ? undefined : await response.json();
  return payload as T;
}

/**
 * The five profile collections are byte-identical, so they share one implementation.
 *
 * The backend deliberately writes these routes out longhand instead, because endpoints
 * are its public surface and OpenAPI should stay obvious. That argument doesn't reach
 * this file: it is internal glue, the factory is fully typed, and the call sites read
 * the same either way.
 */
export interface Collection<Read, Create, Update> {
  list(): Promise<Read[]>;
  create(body: Create): Promise<Read>;
  update(id: string, body: Update): Promise<Read>;
  remove(id: string): Promise<void>;
  /** Send the ids in the desired order; the server rewrites every position at once. */
  reorder(ids: string[]): Promise<Read[]>;
}

function collection<Read, Create, Update>(
  path: string,
): Collection<Read, Create, Update> {
  return {
    list: () => request<Read[]>(path),
    create: (body) => request<Read>(path, "POST", body),
    update: (id, body) => request<Read>(`${path}/${id}`, "PATCH", body),
    remove: (id) => request<void>(`${path}/${id}`, "DELETE"),
    reorder: (ids) => request<Read[]>(`${path}/order`, "PUT", { ids }),
  };
}

// --- profile ----------------------------------------------------------------

export const profile = {
  /** The whole profile, joined and ordered, in one call. */
  get: () => request<Profile>("/profile"),
  update: (body: UserUpdate) => request<User>("/profile", "PATCH", body),
};

export const education = collection<Education, EducationCreate, EducationUpdate>(
  "/profile/education",
);
export const experiences = collection<
  Experience,
  ExperienceCreate,
  ExperienceUpdate
>("/profile/experiences");
export const skills = collection<Skill, SkillCreate, SkillUpdate>(
  "/profile/skills",
);
export const projects = collection<Project, ProjectCreate, ProjectUpdate>(
  "/profile/projects",
);
export const links = collection<Link, LinkCreate, LinkUpdate>("/profile/links");

/** Bullets have no list route — they arrive nested on their experience. */
export const bullets = {
  create: (experienceId: string, body: ExperienceBulletCreate) =>
    request<ExperienceBullet>(
      `/profile/experiences/${experienceId}/bullets`,
      "POST",
      body,
    ),
  update: (
    experienceId: string,
    bulletId: string,
    body: ExperienceBulletUpdate,
  ) =>
    request<ExperienceBullet>(
      `/profile/experiences/${experienceId}/bullets/${bulletId}`,
      "PATCH",
      body,
    ),
  remove: (experienceId: string, bulletId: string) =>
    request<void>(
      `/profile/experiences/${experienceId}/bullets/${bulletId}`,
      "DELETE",
    ),
  reorder: (experienceId: string, ids: string[]) =>
    request<ExperienceBullet[]>(
      `/profile/experiences/${experienceId}/bullets/order`,
      "PUT",
      { ids },
    ),
};

// --- jobs, resumes, applications --------------------------------------------

export const jobs = {
  extract: (url: string) =>
    request<ExtractionResponse>("/jobs/extract", "POST", { url }),
  /** Correct a mis-parsed field before the posting becomes a resume. */
  update: (id: string, body: JobPostingUpdate) =>
    request<JobPosting>(`/jobs/${id}`, "PATCH", body),
};

export const resumes = {
  /**
   * Long and synchronous — roughly 10–55s, depending on the posting and whether the
   * guardrail chain forces a retry. Callers need a real loading state.
   */
  generate: (jobPostingId: string) =>
    request<GenerateResumeResponse>("/resumes/generate", "POST", {
      job_posting_id: jobPostingId,
    }),

  // URLs rather than fetches: the preview is an HTML page and the download is a
  // FileResponse, so the browser navigates to or embeds these directly. Putting either
  // through the JSON helper would be wrong, and neither needs the provider headers.
  previewUrl: (id: string) => `${BASE}/resumes/${id}/preview`,
  downloadUrl: (id: string) => `${BASE}/resumes/${id}/download`,
};

export const applications = {
  list: () => request<Application[]>("/applications"),
  /**
   * Returns the existing application when there already is one for the posting —
   * generation creates it, so this would otherwise duplicate the row it means to update.
   */
  save: (body: ApplicationCreate) =>
    request<Application>("/applications", "POST", body),
  update: (id: string, body: ApplicationUpdate) =>
    request<Application>(`/applications/${id}`, "PATCH", body),
  remove: (id: string) => request<void>(`/applications/${id}`, "DELETE"),
};

// --- misc -------------------------------------------------------------------

export const providers = {
  list: () => request<Provider[]>("/providers"),
};

/**
 * Backend liveness — the empty path, so this requests `/api` exactly.
 *
 * Not `"/"`: that would build `/api/`, which Next 308-redirects to `/api`. `fetch`
 * follows it and the call still works, but it costs an extra round trip on every check.
 */
export const health = () => request<Health>("");
