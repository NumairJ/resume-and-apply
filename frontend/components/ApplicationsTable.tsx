"use client";

import { useMemo, useState } from "react";

import { applications as api, resumes } from "@/lib/api";
import { hostname, isoDate } from "@/lib/format";
import { keys, useInvalidatingMutation } from "@/lib/queries";
import { ConfirmModal, Modal } from "@/components/Modal";
import { STATUSES, StatusDot, label } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button, Empty, Input, Select, Textarea, cx } from "@/components/ui";
import type { Application, ApplicationStatus } from "@/types/api";

type SortKey = "company" | "status" | "updated";

const HEADERS: { key: SortKey; label: string; className?: string }[] = [
  { key: "company", label: "Company / Role" },
  { key: "status", label: "Status", className: "w-44" },
  { key: "updated", label: "Updated", className: "w-28" },
];

/**
 * Filtering and sorting are client-side on purpose: this is one person's list of
 * applications, so paging it through the API would add a round trip and a loading
 * state to something that fits comfortably in memory.
 */
export function ApplicationsTable({ rows }: { rows: Application[] }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ApplicationStatus | "">("");
  const [sort, setSort] = useState<SortKey>("updated");
  const [ascending, setAscending] = useState(false);
  const [notesFor, setNotesFor] = useState<Application | null>(null);
  const [deleting, setDeleting] = useState<Application | null>(null);
  const toast = useToast();

  const update = useInvalidatingMutation(
    ({ id, ...body }: { id: string; status?: ApplicationStatus; notes?: string }) =>
      api.update(id, body),
    keys.applications,
    {
      onSuccess: () => toast("Application updated"),
      onError: (error) => toast(error.message, "error"),
    },
  );

  const remove = useInvalidatingMutation(api.remove, keys.applications, {
    onSuccess: () => {
      setDeleting(null);
      toast("Application deleted");
    },
  });

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = rows.filter((row) => {
      if (status && row.status !== status) return false;
      if (!needle) return true;
      return `${row.job_posting.company} ${row.job_posting.title}`
        .toLowerCase()
        .includes(needle);
    });

    const direction = ascending ? 1 : -1;
    return [...filtered].sort((a, b) => {
      if (sort === "company") {
        return a.job_posting.company.localeCompare(b.job_posting.company) * direction;
      }
      if (sort === "status") {
        return (
          (STATUSES.indexOf(a.status) - STATUSES.indexOf(b.status)) * direction
        );
      }
      return (a.updated_at < b.updated_at ? -1 : 1) * direction;
    });
  }, [rows, query, status, sort, ascending]);

  function toggleSort(key: SortKey) {
    if (key === sort) setAscending((value) => !value);
    else {
      setSort(key);
      setAscending(key === "company");
    }
  }

  return (
    <>
      {/* Sized by wrappers rather than by passing a width class to the control. The
          shared CONTROL style sets `w-full`, and which of two width utilities wins is
          decided by their order in the generated stylesheet, not by the order they
          appear in the class attribute — so an override here would be a coin toss. */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="w-72">
          <Input
            placeholder="Filter by company or role"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Filter by company or role"
          />
        </div>
        <div className="w-44">
          <Select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as ApplicationStatus | "")
            }
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </Select>
        </div>
        <span className="tnum ml-auto text-sm text-muted">
          {visible.length} of {rows.length}
        </span>
      </div>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-y border-ink">
            {HEADERS.map((header) => (
              <th
                key={header.key}
                scope="col"
                className={cx("py-2.5 text-left", header.className)}
                aria-sort={
                  sort === header.key
                    ? ascending
                      ? "ascending"
                      : "descending"
                    : "none"
                }
              >
                <button
                  type="button"
                  onClick={() => toggleSort(header.key)}
                  className="label-xs text-muted hover:text-ink"
                >
                  {header.label}
                  <span aria-hidden className="ml-1">
                    {sort === header.key ? (ascending ? "↑" : "↓") : ""}
                  </span>
                </button>
              </th>
            ))}
            <th scope="col" className="label-xs w-56 py-2.5 text-right text-muted">
              Resume
            </th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => {
            const latest = row.resumes.at(-1);
            return (
              <tr key={row.id} className="border-b border-rule align-top">
                <td className="py-4 pr-4">
                  <p className="font-medium">{row.job_posting.company}</p>
                  <p className="text-muted">{row.job_posting.title}</p>
                  <p className="mt-1 flex gap-3 text-xs">
                    <a
                      href={row.job_posting.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent underline underline-offset-4"
                    >
                      {hostname(row.job_posting.source_url)}
                    </a>
                    <button
                      type="button"
                      onClick={() => setNotesFor(row)}
                      className="text-faint hover:text-ink"
                    >
                      {row.notes ? "Notes ✓" : "Add notes"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleting(row)}
                      className="text-faint hover:text-negative"
                    >
                      Delete
                    </button>
                  </p>
                </td>

                <td className="py-4 pr-4">
                  {/* Dot, not a full badge: the select already names the status, and
                      printing the word twice in two lines says nothing extra. */}
                  <span className="flex items-center gap-2">
                    <StatusDot status={row.status} />
                    <Select
                      value={row.status}
                      onChange={(event) =>
                        update.mutate({
                          id: row.id,
                          status: event.target.value as ApplicationStatus,
                        })
                      }
                      aria-label={`Status for ${row.job_posting.company}`}
                    >
                      {STATUSES.map((value) => (
                        <option key={value} value={value}>
                          {label(value)}
                        </option>
                      ))}
                    </Select>
                  </span>
                </td>

                <td className="tnum py-4 pr-4 text-muted">
                  <time dateTime={row.updated_at}>{isoDate(row.updated_at)}</time>
                </td>

                <td className="py-4 text-right">
                  {latest ? (
                    <span className="inline-flex gap-2">
                      <a
                        href={resumes.previewUrl(latest.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Button size="sm">View</Button>
                      </a>
                      <a href={resumes.downloadUrl(latest.id)} download>
                        <Button size="sm">PDF</Button>
                      </a>
                    </span>
                  ) : (
                    <span className="text-xs text-faint">None generated</span>
                  )}
                  {row.resumes.length > 1 && (
                    <p className="tnum mt-1 text-xs text-faint">
                      {row.resumes.length} versions
                    </p>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {visible.length === 0 && (
        <Empty>
          {rows.length === 0
            ? "Nothing tracked yet."
            : "No applications match this filter."}
        </Empty>
      )}

      <NotesModal
        // Keyed on the row so the modal re-mounts with that row's notes as its initial
        // state. Without this the draft persists across rows, and opening a second
        // application would show the first one's text.
        key={notesFor?.id ?? "none"}
        application={notesFor}
        onClose={() => setNotesFor(null)}
        onSave={(notes) => {
          if (notesFor) update.mutate({ id: notesFor.id, notes });
          setNotesFor(null);
        }}
      />

      <ConfirmModal
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
        title="Delete this application?"
      >
        Its generated resumes and their PDFs are deleted too. The job posting itself
        stays until it expires.
      </ConfirmModal>
    </>
  );
}

function NotesModal({
  application,
  onClose,
  onSave,
}: {
  application: Application | null;
  onClose: () => void;
  onSave: (notes: string) => void;
}) {
  // Seeded from the row's saved notes, not empty: the caller re-mounts this component
  // per row. Starting empty would mean opening the modal and pressing Save without
  // typing silently erased whatever was already there.
  const [text, setText] = useState(application?.notes ?? "");

  return (
    <Modal
      open={application !== null}
      onClose={onClose}
      title={application ? `Notes — ${application.job_posting.company}` : "Notes"}
      footer={
        <>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" variant="primary" onClick={() => onSave(text)}>
            Save notes
          </Button>
        </>
      }
    >
      <Textarea
        rows={6}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Referred by…, recruiter name, interview dates"
      />
    </Modal>
  );
}
