"use client";

import { useState } from "react";

import { education, experiences, links, profile, projects, skills } from "@/lib/api";
import { dateRange } from "@/lib/format";
import { keys, useInvalidatingMutation, useProfile } from "@/lib/queries";
import { BulletEditor } from "@/components/BulletEditor";
import { ProfileSection } from "@/components/ProfileSection";
import {
  CATEGORY_LIST_ID,
  SkillCategoryOptions,
  SkillsBulkAdd,
} from "@/components/SkillsBulkAdd";
import { useToast } from "@/components/Toast";
import { Button, Empty, Field, Input, Page, PageHeader, Textarea } from "@/components/ui";
import type { Profile, UserUpdate } from "@/types/api";

export default function SettingsPage() {
  const { data, isPending, isError, error } = useProfile();

  return (
    <Page>
      <PageHeader title="Profile">
        Everything a generated resume is allowed to draw on. The guardrails check every
        draft against this page, so nothing can appear on a resume that is not here.
      </PageHeader>

      {isPending && <Empty>Loading…</Empty>}
      {isError && <Empty>Could not load your profile — {error.message}</Empty>}
      {data && <Sections profile={data} />}
    </Page>
  );
}

function Sections({ profile: data }: { profile: Profile }) {
  return (
    <div className="divide-y divide-rule">
      <PersonalInfo profile={data} />

      <ProfileSection
        title="Experience"
        description="Bullets here are what tailoring selects from — a resume can rephrase one but never invent one."
        items={data.experiences}
        collection={experiences}
        addLabel="Add role"
        blank={() => ({
          company: "",
          title: "",
          location: null,
          start_date: "",
          end_date: null,
          position: data.experiences.length,
        })}
        view={(item) => (
          <>
            <p className="font-medium">
              {item.title} <span className="text-muted">— {item.company}</span>
            </p>
            <p className="tnum mt-0.5 text-sm text-muted">
              {dateRange(item.start_date, item.end_date)}
              {item.location && ` · ${item.location}`}
            </p>
          </>
        )}
        form={(draft, set) => (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Title">
                <Input
                  required
                  value={draft.title}
                  onChange={(e) => set({ title: e.target.value })}
                />
              </Field>
              <Field label="Company">
                <Input
                  required
                  value={draft.company}
                  onChange={(e) => set({ company: e.target.value })}
                />
              </Field>
              <Field label="Start date">
                <Input
                  type="date"
                  required
                  value={draft.start_date}
                  onChange={(e) => set({ start_date: e.target.value })}
                />
              </Field>
              <Field label="End date" hint="Leave empty if this is your current role">
                <Input
                  type="date"
                  value={draft.end_date ?? ""}
                  onChange={(e) => set({ end_date: e.target.value || null })}
                />
              </Field>
            </div>
            <Field label="Location">
              <Input
                value={draft.location ?? ""}
                onChange={(e) => set({ location: e.target.value || null })}
              />
            </Field>
          </>
        )}
        nested={(item) => <BulletEditor experience={item} />}
      />

      <ProfileSection
        title="Education"
        items={data.education}
        collection={education}
        addLabel="Add education"
        blank={() => ({
          school: "",
          degree: "",
          field_of_study: null,
          start_date: null,
          end_date: null,
          gpa: null,
          position: data.education.length,
        })}
        view={(item) => (
          <>
            <p className="font-medium">
              {item.degree}
              {item.field_of_study && `, ${item.field_of_study}`}
              <span className="text-muted"> — {item.school}</span>
            </p>
            <p className="tnum mt-0.5 text-sm text-muted">
              {dateRange(item.start_date, item.end_date)}
            </p>
          </>
        )}
        form={(draft, set) => (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="School">
                <Input
                  required
                  value={draft.school}
                  onChange={(e) => set({ school: e.target.value })}
                />
              </Field>
              <Field label="Degree">
                <Input
                  required
                  value={draft.degree}
                  onChange={(e) => set({ degree: e.target.value })}
                />
              </Field>
              <Field label="Field of study">
                <Input
                  value={draft.field_of_study ?? ""}
                  onChange={(e) => set({ field_of_study: e.target.value || null })}
                />
              </Field>
              <Field label="GPA">
                <Input
                  value={draft.gpa ?? ""}
                  onChange={(e) => set({ gpa: e.target.value || null })}
                />
              </Field>
              <Field label="Start date">
                <Input
                  type="date"
                  value={draft.start_date ?? ""}
                  onChange={(e) => set({ start_date: e.target.value || null })}
                />
              </Field>
              <Field label="End date">
                <Input
                  type="date"
                  value={draft.end_date ?? ""}
                  onChange={(e) => set({ end_date: e.target.value || null })}
                />
              </Field>
            </div>
          </>
        )}
      />

      {/* One datalist serves both category inputs — the single-skill form below and the
          bulk panel's — so whatever you have already typed is offered in both places. */}
      <SkillCategoryOptions skills={data.skills} />

      <ProfileSection
        title="Skills"
        description="A resume may only list skills that appear here — this is a set-membership check, not a judgement call."
        items={data.skills}
        collection={skills}
        addLabel="Add skill"
        actions={<SkillsBulkAdd skills={data.skills} />}
        groupBy={(item) => item.category?.trim() ?? ""}
        blank={() => ({ name: "", category: null, position: data.skills.length })}
        view={(item) => <p>{item.name}</p>}
        form={(draft, set) => (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Skill">
              <Input
                required
                value={draft.name}
                onChange={(e) => set({ name: e.target.value })}
              />
            </Field>
            <Field label="Category" hint="Languages, Databases, Infrastructure…">
              <Input
                list={CATEGORY_LIST_ID}
                value={draft.category ?? ""}
                onChange={(e) => set({ category: e.target.value || null })}
              />
            </Field>
          </div>
        )}
      />

      <ProfileSection
        title="Projects"
        items={data.projects}
        collection={projects}
        addLabel="Add project"
        blank={() => ({
          name: "",
          description: null,
          url: null,
          start_date: null,
          end_date: null,
          position: data.projects.length,
        })}
        view={(item) => (
          <>
            <p className="font-medium">{item.name}</p>
            {item.description && (
              <p className="mt-0.5 text-sm text-muted">{item.description}</p>
            )}
          </>
        )}
        form={(draft, set) => (
          <>
            <Field label="Name">
              <Input
                required
                value={draft.name}
                onChange={(e) => set({ name: e.target.value })}
              />
            </Field>
            <Field label="Description">
              <Textarea
                rows={2}
                value={draft.description ?? ""}
                onChange={(e) => set({ description: e.target.value || null })}
              />
            </Field>
            <Field label="URL">
              <Input
                value={draft.url ?? ""}
                onChange={(e) => set({ url: e.target.value || null })}
              />
            </Field>
          </>
        )}
      />

      <ProfileSection
        title="Links"
        items={data.links}
        collection={links}
        addLabel="Add link"
        blank={() => ({ label: "", url: "", position: data.links.length })}
        view={(item) => (
          <p>
            <span className="font-medium">{item.label}</span>{" "}
            <span className="text-muted">{item.url}</span>
          </p>
        )}
        form={(draft, set) => (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Label">
              <Input
                required
                value={draft.label}
                onChange={(e) => set({ label: e.target.value })}
              />
            </Field>
            <Field label="URL">
              <Input
                required
                value={draft.url}
                onChange={(e) => set({ url: e.target.value })}
              />
            </Field>
          </div>
        )}
      />
    </div>
  );
}

function PersonalInfo({ profile: data }: { profile: Profile }) {
  const [draft, setDraft] = useState<UserUpdate | null>(null);
  const toast = useToast();

  const save = useInvalidatingMutation(profile.update, keys.profile, {
    onSuccess: () => {
      setDraft(null);
      toast("Saved");
    },
    onError: (error) => toast(error.message, "error"),
  });

  if (!draft) {
    return (
      <section className="py-10">
        <div className="mb-5 flex items-baseline justify-between gap-4">
          <h2 className="display text-lg font-semibold">Personal information</h2>
          <Button
            size="sm"
            onClick={() =>
              setDraft({
                full_name: data.full_name,
                email: data.email,
                phone: data.phone,
                location: data.location,
                summary: data.summary,
              })
            }
          >
            Edit
          </Button>
        </div>
        <p className="font-medium">{data.full_name}</p>
        <p className="text-sm text-muted">
          {[data.email, data.phone, data.location].filter(Boolean).join(" · ")}
        </p>
        {data.summary && (
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
            {data.summary}
          </p>
        )}
      </section>
    );
  }

  return (
    <section className="py-10">
      <h2 className="display mb-5 text-lg font-semibold">Personal information</h2>
      <form
        className="max-w-2xl space-y-3 border-l-2 border-ink py-4 pl-4"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(draft);
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Full name">
            <Input
              required
              value={draft.full_name ?? ""}
              onChange={(e) => setDraft({ ...draft, full_name: e.target.value })}
            />
          </Field>
          <Field label="Email">
            <Input
              type="email"
              required
              value={draft.email ?? ""}
              onChange={(e) => setDraft({ ...draft, email: e.target.value })}
            />
          </Field>
          <Field label="Phone">
            <Input
              value={draft.phone ?? ""}
              onChange={(e) => setDraft({ ...draft, phone: e.target.value || null })}
            />
          </Field>
          <Field label="Location">
            <Input
              value={draft.location ?? ""}
              onChange={(e) =>
                setDraft({ ...draft, location: e.target.value || null })
              }
            />
          </Field>
        </div>
        <Field
          label="Summary"
          hint="Optional. The model rewrites this per posting; it may only draw on what is on this page."
        >
          <Textarea
            rows={3}
            value={draft.summary ?? ""}
            onChange={(e) => setDraft({ ...draft, summary: e.target.value || null })}
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={() => setDraft(null)}>
            Cancel
          </Button>
          <Button type="submit" size="sm" variant="primary" disabled={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </section>
  );
}
