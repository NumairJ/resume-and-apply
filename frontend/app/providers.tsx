"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { ToastProvider } from "@/components/Toast";

export default function Providers({ children }: { children: React.ReactNode }) {
  // Created inside useState, not as a module-level constant. A module-level client is
  // shared across requests during server rendering, which would leak one render's cache
  // into another's. This gives each render its own, and the lazy initialiser keeps it
  // from being rebuilt on every re-render.
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // For a locally-run single-user app, refetching every time the tab regains
            // focus is noise rather than freshness.
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}
