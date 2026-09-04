"use client";

import { useState } from "react";

import { jobs } from "@/lib/api";
import { hostname } from "@/lib/format";
import { useInvalidatingMutation } from "@/lib/queries";
import { useToast } from "@/components/Toast";
import { Button, Field, Input, Textarea } from "@/components/ui";
import type { JobPosting, JobPostingUpdate } from "@/types/api";

const METHOD_LABEL: Record<string, string> = {
  jsonld: "the page's own structured data",
  ats_greenhouse: "the Greenhouse API",
  ats_lever: "the Lever API",
  ats_ashby: "the Ashby API",
  llm: "a language model",
};

/**
 * The parsed posting, editable before it becomes a resume.
 *
 * Editable is the point, not a nicety: extraction can mis-read a field, and the
 * guardrails validate the generated resume against *this* record. Fixing it here is
 * far cheaper than discovering it on the PDF.
 */
export function JobDetailsCard({
  job,
  onChanged,
}: {
  job: JobPosting;
  onChanged: (job: JobPosting) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<JobPostingUpdate>({});
  const toast = useToast();

  const save = useInvalidatingMutation(
    (body: JobPostingUpdate) => jobs.update(job.id, body),
    ["job", job.id],
    {
      onSuccess: (updated) => {
        onChanged(updated);
        setEditing(false);
        toast("Job details updated");
      },
      onError: (error) => toast(error.message, "error"),
    },
  );

  function startEditing() {
    setDraft({
      company: job.company,
      title: job.title,
      location: job.location,
      employment_type: job.employment_type,
      salary_range: job.salary_range,
      description: job.description,
      requirements: job.requirements,
    });
    setEditing(true);
  }

  if (editing) {
    return (
      <form
        className="space-y-4 border-t border-ink pt-6"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(draft);
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Company">
            <Input
              value={draft.company ?? ""}
              onChange={(e) => setDraft({ ...draft, company: e.target.value })}
              required
            />
          </Field>
          <Field label="Title">
            <Input
              value={draft.title ?? ""}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              required
            />
          </Field>
          <Field label="Location">
            <Input
              value={draft.location ?? ""}
              onChange={(e) => setDraft({ ...draft, location: e.target.value })}
            />
          </Field>
          <Field label="Employment type">
            <Input
              value={draft.employment_type ?? ""}
              onChange={(e) =>
                setDraft({ ...draft, employment_type: e.target.value })
              }
            />
          </Field>
        </div>
        <Field label="Salary range">
          <Input
            value={draft.salary_range ?? ""}
            onChange={(e) => setDraft({ ...draft, salary_range: e.target.value })}
          />
        </Field>
        <Field label="Description">
          <Textarea
            rows={10}
            value={draft.description ?? ""}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
          />
        </Field>
        <Field label="Requirements">
          <Textarea
            rows={5}
            value={draft.requirements ?? ""}
            onChange={(e) => setDraft({ ...draft, requirements: e.target.value })}
          />
        </Field>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
    );
  }

  return (
    <div className="border-t border-ink pt-6">
      <div className="flex items-start justify-between gap-6">
        <div>
          <p className="label-xs text-muted">{job.company}</p>
          <h2 className="display mt-1 text-2xl font-semibold">{job.title}</h2>
          <p className="mt-2 text-sm text-muted">
            {[job.location, job.employment_type, job.salary_range]
              .filter(Boolean)
              .join(" · ") || "No location given"}
          </p>
        </div>
        <Button size="sm" onClick={startEditing}>
          Edit details
        </Button>
      </div>

      <p className="mt-4 text-xs text-faint">
        Read from {METHOD_LABEL[job.extraction_method] ?? job.extraction_method} ·{" "}
        <a
          href={job.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-accent underline underline-offset-4"
        >
          {hostname(job.source_url)}
        </a>
      </p>

      {job.description && (
        <details className="mt-6 border-t border-rule pt-4">
          <summary className="label-xs cursor-pointer text-muted">
            Description
          </summary>
          <p className="mt-3 max-h-80 overflow-y-auto text-sm leading-relaxed whitespace-pre-line text-muted">
            {job.description}
          </p>
        </details>
      )}
    </div>
  );
}
