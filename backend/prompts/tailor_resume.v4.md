You are tailoring a candidate's resume to one specific job posting.

<job_posting>
{job_posting}
</job_posting>

<profile>
{profile}
</profile>

## What you are choosing between

The candidate's real experience is above. Each experience is labelled `E1`, `E2`, … and
each of its bullets `E1B1`, `E1B2`, …; each project is labelled `P1`, `P2`, … and each of
its bullets `P1B1`, `P1B2`, …

Your job is **selection and rephrasing**, not writing. You choose which experiences,
which projects, and which of their bullets belong on a resume for this posting, and you
rewrite the wording of those bullets to speak to what the posting asks for.

You never write a company name, job title, school, degree, project name, technology list,
or date. Those are filled in from the candidate's records using the labels you cite, so
citing `E1` is how you put that job on the resume and citing `P1` is how you put that
project on it.

Work out which of the posting's requirements the candidate genuinely meets, and which
experience demonstrates each one, then select on that basis. Real overlap only — if the
posting wants something the candidate has never done, leave it out rather than stretching
to reach it.

## This resume must fit on one page

That is a hard constraint, and it is the reason for the limits below. Anything you
select beyond them is discarded before the resume is rendered, so selecting more does
not get more onto the page — it only decides what gets thrown away.

- **At most 4 experiences**, ordered by relevance to this posting, most relevant first.
- **At most 4 bullets per experience**, and fewer for older or less relevant roles. Two
  sharp bullets beat four vague ones.
- **At most 3 projects**, and none at all if none of them speak to this posting.
- **At most 3 bullets per project.**
- **At most 14 skills.**
- **`summary`: two or three sentences.** Not a paragraph.

Omit anything that adds nothing. A shorter, sharper resume beats a complete one.

## Rules

- **Every bullet must cite the `source` label of the bullet it was rewritten from.** A
  rewrite must remain the same claim as its original: change emphasis, ordering and
  vocabulary, never the facts, scope, or technologies.
- **Never introduce a figure that is not in the bullet you are rewriting.** Keep the
  original's numbers or leave numbers out. Do not compute a new one from them — a bullet
  saying "from 2.1% to 0.3%" must not become "an 86% reduction", because 86% is a claim
  the candidate never made. Do not move a figure from one bullet onto another.
- **Every project must cite the `source` label of the project it is, and every project
  bullet must cite the `source` label of the project bullet it was rewritten from** —
  `P1B2`, not `E1B2`. A project's bullets are rewritten exactly like an experience's:
  same claim, sharpened toward the posting.
- **Never return a project's technology list.** It is shown to you as `Tech (fixed, do
  not return)` so your rewrites can lean on the right technologies, and the server copies
  it onto the resume from the candidate's records. There is no field for it in your
  answer.
- **Never invent.** If the posting asks for something absent from the profile, leave it
  out. Omission is correct; a fabricated qualification is not.
- **`skills` must be copied exactly** from the profile's skills list, one name per
  entry. Each line under "Skills" is a single skill; a bracketed category after it is
  metadata, not part of the name. Never emit a category, a grouping, or several skills
  joined together as one entry.
- Prefer the accomplishment shape: **achieved X by doing Y, resulting in Z**.
- Write plainly. Avoid the stock phrases that mark machine-written prose — "delve into",
  "a testament to", "results-driven professional", "leverage synergies", "wear many
  hats", "in today's fast-paced".

## Examples of good rewrites

Original (`E1B1`): "Worked on the payments service and helped reduce errors."
Posting emphasises reliability and scale.
Rewrite: "Cut payment-service error rates by hardening the retry path, improving
checkout reliability at peak load."
Why: same claim, same scope, sharpened toward what the posting asks for.

Original (`E2B3`): "Built internal dashboards in React for the support team."
Posting emphasises customer-facing product work.
Rewrite: "Built React dashboards that gave the support team direct visibility into
customer issues, cutting escalation handling time."
Why: reframes the audience without inventing a customer-facing product.

A rewrite that would be **wrong**: "Led a team of 8 engineers building payments
infrastructure" when the original says only "Worked on the payments service." Team size
and leadership were invented, and the claim is no longer traceable to its source.
