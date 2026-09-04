"use client";

import { useState } from "react";

import { bullets as api } from "@/lib/api";
import { keys, useInvalidatingMutation } from "@/lib/queries";
import { useToast } from "@/components/Toast";
import { Button, Textarea } from "@/components/ui";
import type { Experience } from "@/types/api";

/**
 * The bullets under one experience.
 *
 * Its own component rather than another `ProfileSection` because bullets are nested:
 * every call carries the experience id, so the flat `Collection` shape does not fit.
 *
 * These are the load-bearing rows of the whole project. Tailoring is a *selection*
 * problem over exactly these strings — the model may rewrite one but may not invent
 * one — so what is written here bounds what any generated resume can say.
 */
export function BulletEditor({ experience }: { experience: Experience }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [text, setText] = useState("");
  const toast = useToast();

  const options = { onError: (error: Error) => toast(error.message, "error") };

  const create = useInvalidatingMutation(
    (body: { text: string; position: number }) => api.create(experience.id, body),
    keys.profile,
    { ...options, onSuccess: close },
  );

  const update = useInvalidatingMutation(
    ({ id, text: value }: { id: string; text: string }) =>
      api.update(experience.id, id, { text: value }),
    keys.profile,
    { ...options, onSuccess: close },
  );

  const remove = useInvalidatingMutation(
    (id: string) => api.remove(experience.id, id),
    keys.profile,
    options,
  );

  const reorder = useInvalidatingMutation(
    (ids: string[]) => api.reorder(experience.id, ids),
    keys.profile,
    options,
  );

  function close() {
    setEditing(null);
    setText("");
  }

  function move(index: number, by: -1 | 1) {
    const next = [...experience.bullets];
    const target = index + by;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    reorder.mutate(next.map((bullet) => bullet.id));
  }

  function submit() {
    const value = text.trim();
    if (!value) return;
    if (editing === "new") {
      create.mutate({ text: value, position: experience.bullets.length });
    } else if (editing) {
      update.mutate({ id: editing, text: value });
    }
  }

  const editor = (
    <div className="space-y-2 border-l-2 border-ink py-2 pl-4">
      <Textarea
        rows={2}
        autoFocus
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Achieved X by doing Y, resulting in Z"
        aria-label="Bullet text"
      />
      <div className="flex justify-end gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={close}>
          Cancel
        </Button>
        <Button type="button" size="sm" variant="primary" onClick={submit}>
          Save bullet
        </Button>
      </div>
    </div>
  );

  return (
    <div className="mt-3 ml-1 border-l border-rule pl-5">
      <ul className="space-y-1">
        {experience.bullets.map((bullet, index) => (
          <li key={bullet.id}>
            {editing === bullet.id ? (
              editor
            ) : (
              <div className="group flex items-start gap-2 py-1">
                <span aria-hidden className="pt-1 text-xs text-faint">
                  —
                </span>
                <p className="flex-1 text-sm leading-relaxed">{bullet.text}</p>
                <span className="flex shrink-0 items-center gap-0.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Move bullet up"
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                  >
                    ↑
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Move bullet down"
                    disabled={index === experience.bullets.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    ↓
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setEditing(bullet.id);
                      setText(bullet.text);
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="hover:text-negative"
                    onClick={() => remove.mutate(bullet.id)}
                  >
                    ×
                  </Button>
                </span>
              </div>
            )}
          </li>
        ))}
      </ul>

      {editing === "new" ? (
        <div className="mt-2">{editor}</div>
      ) : (
        <Button
          size="sm"
          variant="ghost"
          className="mt-1"
          onClick={() => {
            setEditing("new");
            setText("");
          }}
        >
          + Add bullet
        </Button>
      )}
    </div>
  );
}
