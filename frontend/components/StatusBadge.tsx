import type { ApplicationStatus } from "@/types/api";
import { cx } from "@/components/ui";

export const STATUSES: ApplicationStatus[] = [
  "saved",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
];

// A dot and a word, not a filled pill. Six saturated pills would fight everything else
// on the page; colour here marks the two outcomes that actually matter and the one
// state that is live, and stays neutral for the rest.
const DOT: Record<ApplicationStatus, string> = {
  saved: "text-faint",
  applied: "text-ink",
  interviewing: "text-accent",
  offer: "text-positive",
  rejected: "text-negative",
  withdrawn: "text-faint",
};

export function label(status: ApplicationStatus): string {
  return status[0].toUpperCase() + status.slice(1);
}

/**
 * The dot alone, for places that already name the status — the table pairs it with a
 * `<select>`, where repeating the word would say the same thing twice in two lines.
 */
export function StatusDot({ status }: { status: ApplicationStatus }) {
  return (
    <span
      aria-hidden
      className={cx("text-[0.6rem] leading-none", DOT[status])}
      title={label(status)}
    >
      ●
    </span>
  );
}

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm whitespace-nowrap">
      <StatusDot status={status} />
      <span className={status === "withdrawn" ? "text-muted" : undefined}>
        {label(status)}
      </span>
    </span>
  );
}
