"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { cx } from "@/components/ui";

type Tone = "info" | "error";

interface Toast {
  id: number;
  message: string;
  tone: Tone;
}

const ToastContext = createContext<((message: string, tone?: Tone) => void) | null>(
  null,
);

/** Mutations are fire-and-forget from the user's point of view; this is the receipt. */
export function useToast() {
  const toast = useContext(ToastContext);
  if (!toast) throw new Error("useToast must be used inside <ToastProvider>");
  return toast;
}

const DISMISS_AFTER = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((message: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message, tone }]);
    setTimeout(
      () => setToasts((current) => current.filter((t) => t.id !== id)),
      DISMISS_AFTER,
    );
  }, []);

  // Memoised so every consumer isn't re-rendered on each toast state change.
  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        // polite, not assertive: these confirm what the user just did, so they should
        // wait for a pause rather than interrupt whatever is being read.
        aria-live="polite"
        className="pointer-events-none fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center gap-2"
      >
        {toasts.map((toast) => (
          <p
            key={toast.id}
            className={cx(
              "rounded-[2px] border bg-paper px-3.5 py-2 text-sm",
              toast.tone === "error"
                ? "border-negative text-negative"
                : "border-ink text-ink",
            )}
          >
            {toast.message}
          </p>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
