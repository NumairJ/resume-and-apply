import { describe, expect, it } from "vitest";

import { dateRange, hostname, isoDate, longDate, maskKey } from "@/lib/format";

// These run with TZ=America/Toronto (set in vitest.config.mts), which is the whole
// point: in UTC every one of these would pass even with the bug they exist to catch.
describe("dates west of Greenwich", () => {
  it("does not shift a calendar date back a day", () => {
    // Regression. `new Date("2021-03-01")` is UTC midnight, which is 7pm on 28 Feb in
    // Toronto — so the settings page displayed every start date one month early.
    expect(dateRange("2021-03-01", "2024-06-01")).toBe("Mar 2021 – Jun 2024");
    expect(isoDate("2021-03-01")).toBe("2021-03-01");
    expect(longDate("2019-05-01")).toBe("1 May 2019");
  });

  it("still handles the first of a month at both ends of the year", () => {
    expect(isoDate("2026-01-01")).toBe("2026-01-01");
    expect(isoDate("2025-12-31")).toBe("2025-12-31");
  });

  it("renders a timestamp as its local calendar day", () => {
    // 20:30 UTC is 15:30 in Toronto on the same date.
    expect(isoDate("2026-09-04T20:30:00Z")).toBe("2026-09-04");
  });
});

describe("dateRange", () => {
  it("calls an open-ended role present", () => {
    expect(dateRange("2021-03-01", null)).toBe("Mar 2021 – Present");
  });

  it("drops the separator when there is no start date", () => {
    expect(dateRange(null, "2019-05-01")).toBe("May 2019");
  });

  it("is empty when there are no dates at all", () => {
    expect(dateRange(null, null)).toBe("");
  });
});

describe("maskKey", () => {
  it("shows enough to recognise the key and not enough to use it", () => {
    const key = "sk-ant-api03-abcdefghijklmnop9f2a";
    const masked = maskKey(key);

    expect(masked).toBe("sk-ant-…9f2a");
    expect(masked).not.toContain("abcdefghijklmnop");
  });

  it("reveals nothing at all from a short key", () => {
    expect(maskKey("short")).toBe("•••••");
  });
});

describe("hostname", () => {
  it("strips the scheme, path and www", () => {
    expect(hostname("https://www.boards.example.com/jobs/1")).toBe(
      "boards.example.com",
    );
  });

  it("returns the input unchanged when it is not a URL", () => {
    expect(hostname("not a url")).toBe("not a url");
  });
});
