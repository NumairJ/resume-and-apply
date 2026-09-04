/**
 * The provider switcher's state, which lives in localStorage and nowhere else.
 *
 * A module rather than component state because two unrelated places need it: the
 * switcher writes it, and `lib/api.ts:request()` reads it on every call to attach the
 * `X-LLM-*` headers. Keeping the key and the parsing in one place stops those two
 * drifting apart.
 *
 * Exposed as an external store so React can subscribe with `useSyncExternalStore`,
 * which is the right tool for this: it has a dedicated server snapshot, so the
 * server-rendered HTML and the first client render agree and no hydration error is
 * possible.
 */

export const PROVIDER_STORAGE_KEY = "resume-and-apply.llm";

export interface ProviderSettings {
  provider?: string;
  model?: string;
  apiKey?: string;
}

/** The server has no localStorage, and this identity must be stable across calls. */
const EMPTY: ProviderSettings = Object.freeze({});

const listeners = new Set<() => void>();

// getSnapshot must return a cached value with a stable identity — returning a freshly
// parsed object every call makes useSyncExternalStore re-render forever.
let cachedRaw: string | null = null;
let cached: ProviderSettings = EMPTY;

export function readProviderSettings(): ProviderSettings {
  if (typeof window === "undefined") return EMPTY;

  const raw = window.localStorage.getItem(PROVIDER_STORAGE_KEY);
  if (raw === cachedRaw) return cached;

  cachedRaw = raw;
  try {
    cached = raw ? (JSON.parse(raw) as ProviderSettings) : EMPTY;
  } catch {
    // A corrupted entry must not break every request in the app.
    cached = EMPTY;
  }
  return cached;
}

export function getServerSnapshot(): ProviderSettings {
  return EMPTY;
}

export function writeProviderSettings(settings: ProviderSettings): void {
  const cleaned: ProviderSettings = {
    provider: settings.provider || undefined,
    model: settings.model || undefined,
    apiKey: settings.apiKey?.trim() || undefined,
  };
  window.localStorage.setItem(PROVIDER_STORAGE_KEY, JSON.stringify(cleaned));
  emit();
}

export function clearProviderSettings(): void {
  window.localStorage.removeItem(PROVIDER_STORAGE_KEY);
  emit();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  // `storage` fires only in *other* tabs, which is why writes above emit explicitly.
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function emit(): void {
  for (const listener of listeners) listener();
}

/** The `X-LLM-*` headers for a request, or nothing when no key is configured. */
export function providerHeaders(): Record<string, string> {
  const settings = readProviderSettings();
  const headers: Record<string, string> = {};
  if (settings.provider) headers["X-LLM-Provider"] = settings.provider;
  if (settings.model) headers["X-LLM-Model"] = settings.model;
  if (settings.apiKey) headers["X-LLM-Api-Key"] = settings.apiKey;
  return headers;
}
