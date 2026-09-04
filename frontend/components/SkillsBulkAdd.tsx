"use client";

import { useState } from "react";

import { skills as api } from "@/lib/api";
import { keys, useInvalidatingMutation } from "@/lib/queries";
import { existingCategories, newSkillNames, parseSkillNames } from "@/lib/skills";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Button, Field, Input, Textarea } from "@/components/ui";
import type { Skill } from "@/types/api";

export const CATEGORY_LIST_ID = "skill-categories";

/**
 * Paste a list of skills instead of adding them one at a time.
 *
 * One category applies to the whole batch, which is the shape the task actually has:
 * you paste your languages, then your databases. Adding twenty-five skills through the
 * single-row form is twenty-five open-type-type-save cycles, which is what prompted
 * this.
 */
export function SkillsBulkAdd({ skills: existing }: { skills: Skill[] }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const toast = useToast();

  const parsed = parseSkillNames(text);
  const fresh = newSkillNames(parsed, existing);
  const duplicates = parsed.length - fresh.length;

  const add = useInvalidatingMutation(
    async (names: string[]) => {
      // Sequential, and failures are collected rather than thrown. A partial batch
      // still has to invalidate the profile query — throwing on the twentieth of
      // twenty-five would skip that and leave the page showing a stale list.
      let added = 0;
      let failed = 0;
      for (const [index, name] of names.entries()) {
        try {
          await api.create({
            name,
            category: category.trim() || null,
            position: existing.length + index,
          });
          added += 1;
        } catch {
          failed += 1;
        }
      }
      return { added, failed };
    },
    keys.profile,
    {
      onSuccess: ({ added, failed }) => {
        const parts = [`Added ${added} skill${added === 1 ? "" : "s"}`];
        if (duplicates) parts.push(`${duplicates} already there`);
        if (failed) parts.push(`${failed} failed`);
        toast(parts.join(" · "), failed ? "error" : "info");
        close();
      },
    },
  );

  function close() {
    setOpen(false);
    setText("");
    setCategory("");
  }

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        Paste a list
      </Button>

      <Modal
        open={open}
        onClose={close}
        title="Add several skills"
        footer={
          <>
            <Button type="button" variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={fresh.length === 0 || add.isPending}
              onClick={() => add.mutate(fresh)}
            >
              {add.isPending ? "Adding…" : `Add ${fresh.length}`}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field
            label="Skills"
            hint="Separated by commas or new lines. Ones you already have are skipped."
          >
            <Textarea
              rows={5}
              autoFocus
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Python, Go, Rust, TypeScript"
            />
          </Field>

          <Field label="Category" hint="Applied to everything in this batch. Optional.">
            <Input
              list={CATEGORY_LIST_ID}
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              placeholder="Languages"
            />
          </Field>

          {/* Say what will happen before it happens — the count is the whole reassurance
              that the separators were understood the way you meant them. */}
          <p className="text-sm text-muted" aria-live="polite">
            {parsed.length === 0
              ? "Nothing to add yet."
              : `${fresh.length} to add` +
                (duplicates ? `, ${duplicates} already in your profile` : "")}
          </p>
        </div>
      </Modal>
    </>
  );
}

/** The shared `<datalist>` behind both category inputs. */
export function SkillCategoryOptions({ skills }: { skills: Skill[] }) {
  return (
    <datalist id={CATEGORY_LIST_ID}>
      {existingCategories(skills).map((category) => (
        <option key={category} value={category} />
      ))}
    </datalist>
  );
}
