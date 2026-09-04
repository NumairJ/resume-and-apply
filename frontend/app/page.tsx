"use client";

import { useQuery } from "@tanstack/react-query";

import { health } from "@/lib/api";

/**
 * Still just the backend health check — Phase 7 replaces this with the real landing
 * page. It goes through React Query and the typed client rather than a raw `fetch` so
 * that the provider, the client, the types and Tailwind are all actually exercised;
 * a page left on `useEffect` would leave every one of them unverified.
 */
export default function Home() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: health,
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-8 py-24">
      <h1 className="text-4xl font-semibold tracking-tight text-balance">
        Resume and Apply
      </h1>
      <p className="text-lg text-balance opacity-70">
        {isPending && "Checking backend status…"}
        {isError && "⚠️ Could not reach the backend. Is it running?"}
        {data && `✅ ${data.message}`}
      </p>
    </main>
  );
}
