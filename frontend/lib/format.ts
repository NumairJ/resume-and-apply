/** Display formatting. Dates arrive from the backend as ISO strings, never as `Date`. */

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

function parse(value: string | null | undefined): Date | null {
  if (!value) return null;

  // A bare YYYY-MM-DD is a calendar date, not an instant, and must be built from local
  // parts. `new Date("2021-03-01")` parses it as *UTC* midnight, so formatting it in
  // any negative-offset timezone lands on the previous day — a start date of March
  // 2021 renders as "Feb 2021". Every profile date arrives in this form.
  if (DATE_ONLY.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/**
 * `2026-09-04` for table columns. Deliberately ISO rather than a localised format:
 * it sorts as text, it is unambiguous between British and American readers, and with
 * tabular numerals it aligns down the column.
 *
 * Built from local parts rather than `toISOString()`, which would re-introduce the
 * same shift for timestamps late in the day.
 */
export function isoDate(value: string | null | undefined): string {
  const date = parse(value);
  if (!date) return "—";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** `4 September 2026` — for prose, where an ISO string reads like a serial number. */
export function longDate(value: string | null | undefined): string {
  const date = parse(value);
  return date
    ? date.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "—";
}

export function monthYear(value: string | null | undefined): string {
  const date = parse(value);
  return date
    ? date.toLocaleDateString("en-GB", { month: "short", year: "numeric" })
    : "";
}

export function dateRange(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  const from = monthYear(start);
  const to = end ? monthYear(end) : "Present";
  if (!from) return to === "Present" ? "" : to;
  return `${from} – ${to}`;
}

/**
 * `sk-ant-…9f2a`. Enough to recognise which key is loaded, not enough to use if
 * someone is looking over your shoulder or at a screen recording.
 */
export function maskKey(key: string): string {
  if (key.length <= 8) return "•".repeat(key.length);
  return `${key.slice(0, 7)}…${key.slice(-4)}`;
}

/** Hostname only — a full posting URL is far too long for a table cell. */
export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
