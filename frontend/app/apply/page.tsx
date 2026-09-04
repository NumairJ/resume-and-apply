"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, applications, jobs, resumes } from "@/lib/api";
import { longDate } from "@/lib/format";
import { keys, useInvalidatingMutation } from "@/lib/queries";
import { JobDetailsCard } from "@/components/JobDetailsCard";
import { ResumePreview } from "@/components/ResumePreview";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button, Input, Page, PageHeader } from "@/components/ui";
import type {
  DuplicateWarning,
  GenerateResumeResponse,
  JobPosting,
} from "@/types/api";

/**
 * Seconds elapsed since a mutation was submitted. Generation runs long enough that a
 * spinner alone leaves you wondering whether it has hung.
 *
 * Derived from React Query's `submittedAt` timestamp rather than a counter reset on
 * start: resetting would mean a synchronous setState in the effect body. Pairing the
 * count with the timestamp it belongs to is what stops a previous run's value showing
 * for the first second of the next one.
 */
function useElapsed(submittedAt: number, running: boolean): number {
  const [state, setState] = useState({ since: 0, seconds: 0 });

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(
      () =>
        setState({
          since: submittedAt,
          seconds: Math.floor((Date.now() - submittedAt) / 1000),
        }),
      500,
    );
    return () => clearInterval(timer);
  }, [submittedAt, running]);

  return state.since === submittedAt ? state.seconds : 0;
}

/** The backend's structured 422s carry the actual reasons; show them, not a shrug. */
function ErrorNotice({ error }: { error: Error }) {
  const reasons = error instanceof ApiError ? error.reasons : [];
  const noProvider = error instanceof ApiError && error.status === 503;

  return (
    <div className="border-l-2 border-negative py-1 pl-4">
      <p className="text-sm text-negative">{error.message}</p>
      {reasons.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm text-muted">
          {reasons.map((reason) => (
            <li key={reason}>— {reason}</li>
          ))}
        </ul>
      )}
      {noProvider && (
        <p className="mt-2 text-sm text-muted">
          Add an API key with the button in the top right.
        </p>
      )}
    </div>
  );
}

function DuplicateNotice({
  duplicate,
  onDismiss,
}: {
  duplicate: DuplicateWarning;
  onDismiss: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-6 border-l-2 border-ink py-1 pl-4">
      <p className="text-sm">
        You already tracked{" "}
        <strong className="font-semibold">
          {duplicate.title} at {duplicate.company}
        </strong>{" "}
        on {longDate(duplicate.first_seen)} — <StatusBadge status={duplicate.status} />
        <span className="mt-1 block text-muted">
          Reapplying is perfectly normal; this is only a heads-up.
        </span>
      </p>
      <Button size="sm" variant="ghost" onClick={onDismiss}>
        Continue anyway
      </Button>
    </div>
  );
}

export default function ApplyPage() {
  const [url, setUrl] = useState("");
  const [job, setJob] = useState<JobPosting | null>(null);
  const [duplicate, setDuplicate] = useState<DuplicateWarning | null>(null);
  const [result, setResult] = useState<GenerateResumeResponse | null>(null);
  const toast = useToast();

  const extract = useInvalidatingMutation(jobs.extract, keys.applications, {
    onSuccess: (response) => {
      setJob(response.job);
      setDuplicate(response.duplicate);
      setResult(null);
    },
  });

  const generate = useInvalidatingMutation(resumes.generate, keys.applications, {
    onSuccess: setResult,
  });

  const markApplied = useInvalidatingMutation(
    (id: string) => applications.update(id, { status: "applied" }),
    keys.applications,
    { onSuccess: () => toast("Marked as applied") },
  );

  const elapsed = useElapsed(generate.submittedAt, generate.isPending);

  function reset() {
    setJob(null);
    setDuplicate(null);
    setResult(null);
    setUrl("");
    extract.reset();
    generate.reset();
  }

  return (
    <Page>
      <PageHeader
        title="Apply"
        actions={job ? <Button onClick={reset}>Start over</Button> : undefined}
      >
        Paste a job posting URL. Nothing is tracked until you generate a resume.
      </PageHeader>

      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (url.trim()) extract.mutate(url.trim());
        }}
      >
        <Input
          type="url"
          required
          placeholder="https://job-boards.greenhouse.io/company/jobs/1234567"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          aria-label="Job posting URL"
        />
        <Button
          type="submit"
          variant="primary"
          className="shrink-0"
          disabled={extract.isPending}
        >
          {extract.isPending ? "Reading…" : "Read posting"}
        </Button>
      </form>

      {extract.error && (
        <div className="mt-6">
          <ErrorNotice error={extract.error} />
        </div>
      )}

      {duplicate && (
        <div className="mt-8">
          <DuplicateNotice
            duplicate={duplicate}
            onDismiss={() => setDuplicate(null)}
          />
        </div>
      )}

      {job && (
        <section className="mt-10">
          <JobDetailsCard job={job} onChanged={setJob} />

          <div className="mt-8 border-t border-rule pt-6">
            {generate.isPending ? (
              <div>
                <p className="text-sm">
                  Tailoring your profile to this posting…{" "}
                  <span className="tnum text-muted">{elapsed}s</span>
                </p>
                <p className="mt-1.5 text-sm text-muted">
                  This takes up to a minute. Every draft is checked against your
                  stored history, and a draft that fails is retried with the specific
                  problem named — so a slow run usually means it caught something.
                </p>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <Button
                  variant="primary"
                  onClick={() => generate.mutate(job.id)}
                  disabled={generate.isPending}
                >
                  {result ? "Regenerate" : "Generate resume"}
                </Button>
                {!result && (
                  <p className="text-sm text-muted">
                    Uses only the experience recorded in your{" "}
                    <Link
                      href="/settings"
                      className="text-accent underline underline-offset-4"
                    >
                      profile
                    </Link>
                    .
                  </p>
                )}
              </div>
            )}

            {generate.error && (
              <div className="mt-6">
                <ErrorNotice error={generate.error} />
              </div>
            )}
          </div>
        </section>
      )}

      {result && (
        <section className="mt-12 border-t border-ink pt-8">
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-muted">
              Saved to your applications — generating a resume tracks the job
              automatically.
            </p>
            <div className="flex gap-2">
              <Button
                onClick={() => markApplied.mutate(result.application_id)}
                disabled={markApplied.isPending}
              >
                Mark as applied
              </Button>
              <Link href="/applications">
                <Button>View applications</Button>
              </Link>
            </div>
          </div>

          <ResumePreview result={result} />
        </section>
      )}
    </Page>
  );
}
