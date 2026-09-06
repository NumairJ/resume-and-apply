"use client";

import { resumes } from "@/lib/api";
import { buttonClass } from "@/components/ui";
import type { GenerateResumeResponse } from "@/types/api";

/**
 * The generated resume, with a footer recording what produced it.
 *
 * Rendered in an **iframe**, not injected into the page. `/resumes/{id}/preview`
 * returns a complete document with its own print stylesheet — the literal bytes
 * WeasyPrint turned into the PDF. Injecting it would leak those styles into the app
 * and the app's into it, and the preview would stop being the thing that was printed.
 *
 * There is no "why these bullets" panel any more. The model used to write a rationale
 * explaining its selection; that cost three to five sentences of output on every
 * attempt, and the page it justified is right there to read.
 */
export function ResumePreview({ result }: { result: GenerateResumeResponse }) {
  return (
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

      <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-4 text-xs">
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
          <div key={label} className="flex gap-2">
            <dt className="text-faint">{label}</dt>
            <dd className="tnum text-muted">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
