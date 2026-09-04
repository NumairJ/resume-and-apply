"use client";

import { useState, type ReactNode } from "react";

import type { Collection } from "@/lib/api";
import { keys, useInvalidatingMutation } from "@/lib/queries";
import { ConfirmModal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Button, Empty } from "@/components/ui";

/**
 * One frame for the five profile collections, which are identical in shape: an
 * ordered list of rows, each viewable, editable in place, removable and movable.
 *
 * Each row is read-only until you press Edit, and edits commit only on Save. This is
 * the data the guardrails validate every generated resume against, so a stray
 * keystroke should not be able to rewrite it silently.
 *
 * `Create extends Update` holds for every collection here — each Update type is a
 * Partial of its Create — which is what lets one draft type serve both the add form
 * and the edit form.
 */
export function ProfileSection<
  Read extends { id: string },
  Create extends Update,
  Update,
>({
  title,
  description,
  items,
  collection,
  blank,
  view,
  form,
  nested,
  groupBy,
  actions,
  addLabel = "Add",
}: {
  title: string;
  description?: string;
  items: Read[];
  collection: Collection<Read, Create, Update>;
  /** A fresh draft, with `position` set past the end of the list. */
  blank: () => Create;
  view: (item: Read) => ReactNode;
  form: (draft: Create, set: (patch: Partial<Create>) => void) => ReactNode;
  /** Extra content under a row — used for an experience's bullets. */
  nested?: (item: Read) => ReactNode;
  /**
   * Bucket rows under headings. Only skills use this; without it the list is flat, so
   * the other four sections are unaffected. Return "" for rows that have no group.
   */
  groupBy?: (item: Read) => string;
  /** Extra controls beside the Add button — used for the skills bulk-paste panel. */
  actions?: ReactNode;
  addLabel?: string;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Create | null>(null);
  const [deleting, setDeleting] = useState<Read | null>(null);
  const toast = useToast();

  const options = {
    onError: (error: Error) => toast(error.message, "error"),
  };

  const create = useInvalidatingMutation(collection.create, keys.profile, {
    ...options,
    onSuccess: () => {
      close();
      toast(`${title} added`);
    },
  });

  const update = useInvalidatingMutation(
    ({ id, body }: { id: string; body: Update }) => collection.update(id, body),
    keys.profile,
    {
      ...options,
      onSuccess: () => {
        close();
        toast("Saved");
      },
    },
  );

  const remove = useInvalidatingMutation(collection.remove, keys.profile, {
    ...options,
    onSuccess: () => {
      setDeleting(null);
      toast("Removed");
    },
  });

  const reorder = useInvalidatingMutation(
    collection.reorder,
    keys.profile,
    options,
  );

  function close() {
    setEditing(null);
    setDraft(null);
  }

  function startAdd() {
    setEditing("new");
    setDraft(blank());
  }

  function startEdit(item: Read) {
    setEditing(item.id);
    // Read rows carry `id` alongside the writable fields; it is dropped so it is never
    // sent back in the body. Deleted from a copy rather than destructured out, because
    // the discarded binding would just be an unused variable.
    const body: Record<string, unknown> = { ...item };
    delete body.id;
    setDraft(body as Create);
  }

  /**
   * Items in display order, bucketed when `groupBy` is supplied.
   *
   * One bucket named "" when it is not, so the rendering below has a single shape to
   * deal with rather than two.
   */
  const groups: { label: string; items: Read[] }[] = [];
  for (const item of items) {
    const label = groupBy ? groupBy(item) : "";
    const bucket = groups.find((group) => group.label === label);
    if (bucket) bucket.items.push(item);
    else groups.push({ label, items: [item] });
  }
  // An empty label means uncategorised, and those belong after the named groups rather
  // than wherever the first one happened to fall.
  groups.sort((a, b) => Number(a.label === "") - Number(b.label === ""));

  /**
   * Swap with the neighbour **inside the same group** and send the whole new order.
   *
   * Scoped to the group because moving across a category boundary would look like the
   * grouped view had rejected the change: the row would jump somewhere unrelated, or
   * appear not to move at all once regrouped. The endpoint rewrites every position, so
   * the flattened order of all groups is what gets sent either way.
   */
  function move(label: string, index: number, by: -1 | 1) {
    const group = groups.find((candidate) => candidate.label === label);
    if (!group) return;

    const target = index + by;
    if (target < 0 || target >= group.items.length) return;

    const reordered = [...group.items];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];

    reorder.mutate(
      groups
        .flatMap((candidate) =>
          candidate.label === label ? reordered : candidate.items,
        )
        .map((item) => item.id),
    );
  }

  const editor = draft && (
    <form
      className="space-y-3 border-l-2 border-ink py-4 pl-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (editing === "new") create.mutate(draft);
        else if (editing) update.mutate({ id: editing, body: draft });
      }}
    >
      {form(draft, (patch) => setDraft({ ...draft, ...patch }))}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={close}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          size="sm"
          disabled={create.isPending || update.isPending}
        >
          Save
        </Button>
      </div>
    </form>
  );

  return (
    <section className="py-10">
      <div className="mb-5 flex items-baseline justify-between gap-4">
        <div>
          <h2 className="display text-lg font-semibold">{title}</h2>
          {description && (
            <p className="mt-1 text-sm text-muted">{description}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          <Button size="sm" onClick={startAdd} disabled={editing !== null}>
            {addLabel}
          </Button>
        </div>
      </div>

      {editing === "new" && <div className="mb-4">{editor}</div>}

      {items.length === 0 && editing !== "new" && (
        <Empty>Nothing here yet.</Empty>
      )}

      {groups.map((group) => (
        <div key={group.label || "uncategorised"}>
          {groupBy && (
            <h3 className="label-xs mt-6 text-faint first:mt-0">
              {group.label || "Uncategorised"}
            </h3>
          )}
          <ul>
            {group.items.map((item, index) => (
              <li key={item.id} className="border-t border-rule py-4">
                {editing === item.id ? (
                  editor
                ) : (
                  <>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">{view(item)}</div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label="Move up"
                          disabled={index === 0 || reorder.isPending}
                          onClick={() => move(group.label, index, -1)}
                        >
                          ↑
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label="Move down"
                          disabled={
                            index === group.items.length - 1 || reorder.isPending
                          }
                          onClick={() => move(group.label, index, 1)}
                        >
                          ↓
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => startEdit(item)}
                          disabled={editing !== null}
                        >
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setDeleting(item)}
                          className="hover:text-negative"
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                    {nested?.(item)}
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      <ConfirmModal
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
        title={`Remove this entry?`}
        confirmLabel="Remove"
      >
        Generated resumes already on disk keep whatever they were built from; this only
        changes what future ones can draw on.
      </ConfirmModal>
    </section>
  );
}
