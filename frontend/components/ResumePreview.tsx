"use client";

import { resumes } from "@/lib/api";
import { buttonClass } from "@/components/ui";
import type { GenerateResumeResponse } from "@/types/api";

/**
 * The generated resume, plus the model's account of why it chose what it chose.
 *
 * Rendered in an **iframe**, not injected into the page. `/resumes/{id}/preview`
 * returns a complete document with its own print stylesheet — the literal bytes
 * WeasyPrint turned into the PDF. Injecting it would leak those styles into the app
 * and the app's into it, and the preview would stop being the thing that was printed.
 */
export function ResumePreview({ result }: { result: GenerateResumeResponse }) {
  return (
    <div className="grid gap-10 lg:grid-cols-[3fr_2fr]">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="label-xs text-muted">Preview</h2>
          <a
            href={resumes.downloadUrl(result.resume_id)}
            download
            className={buttonClass("primary", "sm")}
          >
            Download PDF
          </a>
        </div>
        <iframe
          title="Resume preview"
          src={resumes.previewUrl(result.resume_id)}
          className="h-[860px] w-full border border-rule bg-paper"
        />
      </div>

      <aside>
        <h2 className="label-xs text-muted">Why these bullets</h2>
        <p className="mt-3 text-sm leading-relaxed whitespace-pre-line text-muted">
          {result.rationale}
        </p>

        <dl className="mt-8 border-t border-rule pt-4 text-xs">
          {[
            ["Model", result.model],
            ["Provider", result.provider],
            ["Prompt", result.prompt_version],
            [
              "Attempts",
              result.attempts > 1
                ? `${result.attempts} — validation rejected an earlier draft`
                : "1",
            ],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 py-1.5">
              <dt className="text-faint">{label}</dt>
              <dd className="tnum text-right text-muted">{value}</dd>
            </div>
          ))}
        </dl>
      </aside>
    </div>
  );
}
