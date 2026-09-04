/** Display formatting. Dates arrive from the backend as ISO strings, never as `Date`. */

function parse(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * `2026-09-04` for table columns. Deliberately ISO rather than a localised format:
 * it sorts as text, it is unambiguous between British and American readers, and with
 * tabular numerals it aligns down the column.
 */
export function isoDate(value: string | null | undefined): string {
  const date = parse(value);
  return date ? date.toISOString().slice(0, 10) : "—";
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
