/**
 * TypeScript mirrors of the backend's Pydantic schemas.
 *
 * Hand-written and kept in sync deliberately. Generating these from the OpenAPI schema
 * is a reasonable later improvement — it is in the backlog — but it buys tooling and a
 * build step at a point where the schemas have only just stopped changing every phase.
 *
 * Two conventions throughout: UUIDs are `string`, and dates are ISO `string`, because
 * that is what FastAPI serialises them to. A `Date` here would be a lie about what
 * arrives over the wire.
 *
 * Sources: backend/schemas/{profile,application,resume}.py and backend/models/enums.py.
 */

// --- enums ------------------------------------------------------------------

// String-literal unions rather than TS `enum`s, so they compare directly against the
// JSON the backend sends without a conversion step in the middle.
export type ApplicationStatus =
  | "saved"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "withdrawn";

export type ExtractionMethod =
  | "jsonld"
  | "ats_greenhouse"
  | "ats_lever"
  | "ats_ashby"
  | "llm";

// --- profile ----------------------------------------------------------------

export interface User {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  location: string | null;
  summary: string | null;
}

export type UserUpdate = Partial<Omit<User, "id">>;

export interface Education {
  id: string;
  school: string;
  degree: string;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
  gpa: string | null;
  position: number;
}

export type EducationCreate = Omit<Education, "id">;
export type EducationUpdate = Partial<EducationCreate>;

export interface ExperienceBullet {
  id: string;
  text: string;
  position: number;
}

export type ExperienceBulletCreate = Omit<ExperienceBullet, "id">;
export type ExperienceBulletUpdate = Partial<ExperienceBulletCreate>;

export interface Experience {
  id: string;
  company: string;
  title: string;
  location: string | null;
  start_date: string;
  end_date: string | null;
  position: number;
  bullets: ExperienceBullet[];
}

// Bullets may be sent nested on create, but are edited through their own routes after
// that — which is why the update type has no `bullets` at all.
export type ExperienceCreate = Omit<Experience, "id" | "bullets"> & {
  bullets?: ExperienceBulletCreate[];
};
export type ExperienceUpdate = Partial<Omit<Experience, "id" | "bullets">>;

export interface Skill {
  id: string;
  name: string;
  category: string | null;
  position: number;
}

export type SkillCreate = Omit<Skill, "id">;
export type SkillUpdate = Partial<SkillCreate>;

export interface Project {
  id: string;
  name: string;
  description: string | null;
  url: string | null;
  start_date: string | null;
  end_date: string | null;
  position: number;
}

export type ProjectCreate = Omit<Project, "id">;
export type ProjectUpdate = Partial<ProjectCreate>;

export interface Link {
  id: string;
  label: string;
  url: string;
  position: number;
}

export type LinkCreate = Omit<Link, "id">;
export type LinkUpdate = Partial<LinkCreate>;

/** The whole profile in one object — what the tailoring prompt and guardrails consume. */
export interface Profile extends User {
  education: Education[];
  experiences: Experience[];
  skills: Skill[];
  projects: Project[];
  links: Link[];
}

// --- job postings and extraction --------------------------------------------

export interface JobPosting {
  id: string;
  company: string;
  title: string;
  location: string | null;
  employment_type: string | null;
  description: string | null;
  requirements: string | null;
  salary_range: string | null;
  source_url: string;
  extraction_method: ExtractionMethod;
  /** null means permanent — something is tracking this posting. */
  expires_at: string | null;
  created_at: string;
}

/** Only the human-meaningful fields are editable; the rest record how the row came to exist. */
export type JobPostingUpdate = Partial<
  Pick<
    JobPosting,
    | "company"
    | "title"
    | "location"
    | "employment_type"
    | "description"
    | "requirements"
    | "salary_range"
  >
>;

/**
 * Advisory only. The UI offers "continue anyway" — reapplying after a rejection is
 * legitimate, and a false positive must never block a real application.
 */
export interface DuplicateWarning {
  application_id: string;
  status: ApplicationStatus;
  applied_at: string | null;
  first_seen: string;
  company: string;
  title: string;
}

export interface ExtractionResponse {
  job: JobPosting;
  duplicate: DuplicateWarning | null;
  /** True when this URL was already extracted and is still inside its TTL. */
  cached: boolean;
}

// --- applications and resumes -----------------------------------------------

export interface Resume {
  id: string;
  application_id: string;
  file_path: string;
  content_hash: string;
  provider: string;
  model: string;
  prompt_version: string;
  created_at: string;
}

export interface Application {
  id: string;
  status: ApplicationStatus;
  applied_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  job_posting: JobPosting;
  resumes: Resume[];
}

export interface ApplicationCreate {
  job_posting_id: string;
  status?: ApplicationStatus;
  applied_at?: string | null;
  notes?: string | null;
}

export type ApplicationUpdate = Partial<
  Pick<Application, "status" | "applied_at" | "notes">
>;

// --- generation -------------------------------------------------------------

export interface ResumeExperience {
  company: string;
  title: string;
  location: string | null;
  start_date: string;
  end_date: string | null;
  bullets: string[];
}

export interface ResumeEducation {
  school: string;
  degree: string;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface ResumeProject {
  name: string;
  url: string | null;
  start_date: string | null;
  end_date: string | null;
  /** The model's rewrite, or null when the profile records no description to rewrite. */
  description: string | null;
}

export interface ResumeLink {
  label: string;
  url: string;
}

/** The finished resume. Every factual field came from the profile, not the model. */
export interface GeneratedResume {
  full_name: string;
  email: string;
  phone: string | null;
  location: string | null;
  summary: string;
  experiences: ResumeExperience[];
  projects: ResumeProject[];
  education: ResumeEducation[];
  skills: string[];
  links: ResumeLink[];
}

export interface GenerateResumeResponse {
  resume_id: string;
  application_id: string;
  resume: GeneratedResume;
  /** Shown on the Apply page as "why these bullets". Not persisted server-side. */
  rationale: string;
  provider: string;
  model: string;
  prompt_version: string;
  /** More than 1 means the guardrail chain rejected an attempt and the retry fixed it. */
  attempts: number;
}

// --- providers --------------------------------------------------------------

/**
 * `GET /providers` is declared `response_model=list[dict]` on the backend, so OpenAPI
 * describes it only as a bare object — the real shape lives in `registry.available()`.
 * This type is the more honest description of the two.
 */
export interface Provider {
  name: string;
  available_models: string[];
}

// --- misc -------------------------------------------------------------------

export interface Health {
  message: string;
}

/**
 * Errors carry `detail` as either a plain string or a structured object: a guardrail
 * rejection sends `{message, violations}`, a non-posting page sends `{message, reasons}`.
 * Preserving the union is what lets the UI show the actual violations.
 */
export type ErrorDetail =
  | string
  | { message: string; violations?: string[]; reasons?: string[] };
