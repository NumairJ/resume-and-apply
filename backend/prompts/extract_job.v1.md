Extract the job posting details from the page text below.

<page_text>
{page_text}
</page_text>

Rules:

- Report only what the page states. If a field is not present, leave it null rather
  than inferring it. A missing salary is not a reason to estimate one.
- `company` is the hiring organisation, not the job board, recruiting agency, or the
  site the posting is hosted on.
- `title` is the role title alone, without the company name, location, or requisition
  number appended.
- `description` should be the substance of the role — what the work is and what the
  team does — with navigation, legal boilerplate, and equal-opportunity statements
  omitted.
- `requirements` should be the qualifications and experience the posting asks for, kept
  as written. Leave null if the posting does not separate them out.
- `salary_range` should be copied verbatim as the posting expresses it, including
  currency and period. Do not convert or normalise it.
- `employment_type` should be the posting's own wording (for example "Full-time",
  "Contract", "Internship").
