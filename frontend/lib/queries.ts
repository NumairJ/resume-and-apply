/**
 * Query keys and the mutation plumbing around them.
 *
 * Invalidation is defined once here rather than restated in every component. That
 * matters most on Settings: six sections all write into the *same* assembled profile,
 * so every one of them invalidates the single `profile` key and the whole page stays
 * consistent without any component knowing about the others.
 */

"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import { applications, profile, providers } from "@/lib/api";

export const keys = {
  profile: ["profile"] as const,
  applications: ["applications"] as const,
  providers: ["providers"] as const,
};

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: profile.get });
}

export function useApplications() {
  return useQuery({ queryKey: keys.applications, queryFn: applications.list });
}

export function useProviders() {
  return useQuery({
    queryKey: keys.providers,
    queryFn: providers.list,
    // The registered providers cannot change without a backend restart, so refetching
    // them is pure noise.
    staleTime: Infinity,
  });
}

/**
 * A mutation that refreshes one query key when it succeeds.
 *
 * Thin on purpose — it exists so that "which key does this invalidate?" is answered at
 * the call site in one line, instead of each component assembling its own
 * `onSuccess: () => queryClient.invalidateQueries(...)`.
 */
export function useInvalidatingMutation<TData, TVariables>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  invalidate: readonly unknown[],
  options?: Omit<
    UseMutationOptions<TData, Error, TVariables>,
    "mutationFn" | "onSuccess"
  > & {
    onSuccess?: (data: TData, variables: TVariables) => void;
  },
) {
  const queryClient = useQueryClient();
  const { onSuccess, ...rest } = options ?? {};

  return useMutation<TData, Error, TVariables>({
    mutationFn,
    onSuccess: (data, variables) => {
      void queryClient.invalidateQueries({ queryKey: invalidate });
      onSuccess?.(data, variables);
    },
    ...rest,
  });
}
