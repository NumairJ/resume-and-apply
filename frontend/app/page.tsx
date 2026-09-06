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

export default function Home() {
  return (
    <Page>
      <section className="border-b border-rule pb-14">
        <h1 className="display mt-5 max-w-3xl text-5xl leading-[1.05] font-semibold">
          Build Resumes based on your real experience!
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          Paste a job URL. The posting is parsed, your profile is tailored to it, and
          the result is checked against your stored history before you ever see it —
          then tracked as an application with the PDF attached. <br></br>
          Please set up profile first, so that your experience is stored and ready to be tailored to postings.
        </p>
        <div className="mt-8 flex items-center gap-6">
          <Link
            href="/apply"
            className="inline-flex h-10 items-center rounded-[2px] bg-ink px-5 text-sm text-paper transition-colors hover:bg-black"
          >
            Post a job and tailor a resume
          </Link>
          <Link
            href="/settings"
            className="text-sm text-accent underline underline-offset-4"
          >
            Set up your profile
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
    </Page>
  );
}
