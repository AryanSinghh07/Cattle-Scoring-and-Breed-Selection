"use client";

import type { Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useState } from "react";
import { getSupabase } from "./supabase";

type SessionState = {
  /** undefined while loading, null when signed out */
  session: Session | null | undefined;
  /** false when Supabase settings are missing */
  configured: boolean;
};

const SessionContext = createContext<SessionState>({ session: undefined, configured: false });

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const supabase = getSupabase();
  const [session, setSession] = useState<Session | null | undefined>(supabase ? undefined : null);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  return <SessionContext.Provider value={{ session, configured: !!supabase }}>{children}</SessionContext.Provider>;
}

export const useSession = () => useContext(SessionContext);
