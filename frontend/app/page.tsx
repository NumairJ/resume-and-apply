import Link from "next/link";

import { Page } from "@/components/ui";

const STEPS = [
  {
    n: "01",
    title: "Paste a posting",
    body: "Extraction runs cheapest-first: a known job board is read straight from its JSON API, a page with schema.org data is parsed directly, and only what's left reaches a model.",
  },
  {
    n: "02",
    title: "Check the parse",
    body: "The parsed job is editable before anything is generated, so a mis-read company or title gets fixed while it is still cheap to fix.",
  },
  {
    n: "03",
    title: "Generate",
    body: "Your stored experience is tailored to the posting, then validated. A generation that fails validation is retried with the specific failure named, and never returned quietly.",
  },
  {
    n: "04",
    title: "Track it",
    body: "The resume becomes a PDF on disk and an application you can move through saved, applied, interviewing, offer, rejected or withdrawn.",
  },
];

const DECISIONS = [
  {
    title: "The model cannot invent an employer",
    body: "It never writes a company, title, school, degree or date. It returns short reference labels — E1, E1B2 — naming which of your real entries to use, plus rewritten bullet text; the server fills every factual field from the database rows those labels resolve to. Fabrication in structured fields is impossible by construction rather than caught after the fact.",
  },
  {
    title: "Guardrails are hardcoded, not LLM-judged",
    body: "Asking a model whether another model made something up inherits the same failure mode. Every check here is decidable: set membership for skills, token overlap against the source bullet, year membership scoped to the job that claims it. Decidable is what makes “this doesn't fabricate” checkable instead of aspirational.",
  },
  {
    title: "Most postings never reach a model",
    body: "The pipeline tries a job-board adapter, then the page's own structured data, then a weighted heuristic that decides whether this is a job posting at all. A blog post is rejected with reasons before a single token is spent.",
  },
  {
    title: "The preview is the PDF",
    body: "One Jinja2 template renders HTML; WeasyPrint turns those exact bytes into the PDF, and both are kept. What you read on screen and what you send an employer cannot drift apart, because they are the same document.",
  },
];

export default function Home() {
  return (
    <Page>
      <section className="border-b border-rule pb-14">
        <p className="label-xs text-muted">Locally run · Your data stays on your machine</p>
        <h1 className="display mt-5 max-w-3xl text-5xl leading-[1.05] font-semibold">
          Resumes tailored to a posting, from experience you actually have.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          Paste a job URL. The posting is parsed, your profile is tailored to it, and
          the result is checked against your stored history before you ever see it —
          then tracked as an application with the PDF attached.
        </p>
        <div className="mt-8 flex items-center gap-6">
          <Link
            href="/apply"
            className="inline-flex h-10 items-center rounded-[2px] bg-ink px-5 text-sm text-paper transition-colors hover:bg-black"
          >
            Tailor a resume
          </Link>
          <Link
            href="/settings"
            className="text-sm text-accent underline underline-offset-4"
          >
            Set up your profile first
          </Link>
        </div>
      </section>

      <section className="border-b border-rule py-14">
        <h2 className="label-xs text-muted">How it works</h2>
        <ol className="mt-8 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step) => (
            <li key={step.n} className="border-t border-ink pt-4">
              <span className="tnum text-xs text-faint">{step.n}</span>
              <h3 className="mt-2 text-sm font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="py-14">
        <h2 className="label-xs text-muted">Why it is built this way</h2>
        <dl className="mt-8">
          {DECISIONS.map((decision, index) => (
            <div
              key={decision.title}
              className="grid gap-x-10 gap-y-2 border-b border-rule py-7 first:border-t sm:grid-cols-[1fr_2fr]"
            >
              <dt className="flex gap-4">
                <span className="tnum pt-0.5 text-xs text-faint">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="display text-base font-semibold">
                  {decision.title}
                </span>
              </dt>
              <dd className="text-sm leading-relaxed text-muted">{decision.body}</dd>
            </div>
          ))}
        </dl>
      </section>
    </Page>
  );
}
