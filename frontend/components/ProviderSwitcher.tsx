"use client";

import { useState, useSyncExternalStore } from "react";

import { maskKey } from "@/lib/format";
import {
  clearProviderSettings,
  getServerSnapshot,
  readProviderSettings,
  subscribe,
  writeProviderSettings,
  type ProviderSettings,
} from "@/lib/providerSettings";
import { useProviders } from "@/lib/queries";
import { Button, Field, Input, Select } from "@/components/ui";
import { Modal } from "@/components/Modal";

/**
 * Provider, model and API key — held in the browser and nowhere else.
 *
 * Only the *write* side lives here. `lib/api.ts:request()` reads the same store and
 * attaches `X-LLM-Provider/-Model/-Api-Key` to every call, so nothing else in the app
 * has to know this component exists.
 *
 * The store is read through `useSyncExternalStore` rather than an effect: its server
 * snapshot is empty, matching what the server actually renders, so hydration cannot
 * mismatch.
 */
export function ProviderSwitcher() {
  const settings = useSyncExternalStore(
    subscribe,
    readProviderSettings,
    getServerSnapshot,
  );
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<ProviderSettings>({});
  const { data: available } = useProviders();

  function openEditor() {
    setDraft(settings);
    setOpen(true);
  }

  function save() {
    writeProviderSettings(draft);
    setOpen(false);
  }

  const selectedProvider = draft.provider ?? available?.[0]?.name;
  const models =
    available?.find((entry) => entry.name === selectedProvider)?.available_models ??
    [];

  return (
    <>
      <Button size="sm" variant="ghost" onClick={openEditor}>
        <span aria-hidden className={settings.apiKey ? "text-positive" : "text-faint"}>
          ●
        </span>
        {settings.apiKey ? maskKey(settings.apiKey) : "Set API key"}
      </Button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Model provider"
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="button" variant="primary" onClick={save}>
              Save
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Provider">
            <Select
              value={draft.provider ?? ""}
              onChange={(event) =>
                setDraft({ ...draft, provider: event.target.value, model: "" })
              }
            >
              <option value="">Default</option>
              {available?.map((entry) => (
                <option key={entry.name} value={entry.name}>
                  {entry.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Model">
            <Select
              value={draft.model ?? ""}
              onChange={(event) => setDraft({ ...draft, model: event.target.value })}
            >
              <option value="">Default</option>
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="API key"
            hint="Stored in this browser only. It is sent with each request and is never written to the server's database or logs."
          >
            <Input
              type="password"
              autoComplete="off"
              placeholder="sk-ant-…"
              value={draft.apiKey ?? ""}
              onChange={(event) => setDraft({ ...draft, apiKey: event.target.value })}
            />
          </Field>

          {settings.apiKey && (
            <div className="flex items-center justify-between border-t border-rule pt-4">
              <span className="text-sm text-muted">
                Saved key <span className="tnum">{maskKey(settings.apiKey)}</span>
              </span>
              <Button
                type="button"
                size="sm"
                variant="danger"
                onClick={() => {
                  clearProviderSettings();
                  setDraft({});
                }}
              >
                Clear key
              </Button>
            </div>
          )}
        </div>
      </Modal>
    </>
  );
}
