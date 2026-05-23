import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL ?? "http://localhost:54321";
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

type AnyFn = (..._: unknown[]) => unknown;
type FakeChain = {
  select: AnyFn;
  order: AnyFn;
  eq: AnyFn;
  in: AnyFn;
  limit: AnyFn;
  range: AnyFn;
  maybeSingle: () => Promise<{ data: null; error: null }>;
  then: (
    onFulfilled?: (v: { data: unknown[]; error: null }) => unknown,
    onRejected?: (r: unknown) => unknown,
  ) => Promise<unknown>;
};

function makeFakeClient(): SupabaseClient {
  const chain = (): FakeChain => {
    const empty = { data: [] as unknown[], error: null };
    const c: FakeChain = {
      select: () => c,
      order: () => c,
      eq: () => c,
      in: () => c,
      limit: () => c,
      range: () => c,
      maybeSingle: () => Promise.resolve({ data: null, error: null }),
      then: (onFulfilled, onRejected) =>
        Promise.resolve(empty).then(onFulfilled, onRejected),
    };
    return c;
  };
  return {
    from: () => chain(),
    // Minimal stand-in; the UI only uses .from().
  } as unknown as SupabaseClient;
}

export const supabase: SupabaseClient = anon
  ? createClient(url, anon, { auth: { persistSession: false } })
  : makeFakeClient();
