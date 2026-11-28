"use client";

import { getSupabase } from "./supabase";

/** Client for the v2 API (see api/README.md). Shapes mirror the API responses. */

export type View = "side" | "top" | "back";
export type Point = { x: number; y: number; confidence: number };
export type Points = Record<string, Point>;

export type ViewResult = {
  view: View;
  image: { width: number; height: number };
  animal: { label: string; score: number; box: [number, number, number, number] } | null;
  outline: [number, number][];
  facing: "left" | "right" | null;
  points: Points;
  marker: { cm_per_px: number; side_px: number; marker_id: number; side_ratio: number; warnings: string[] } | null;
  warnings: string[];
};

export type Signal = { name: string; description: string; value: number; position: number; weight: number; effect: "thinner" | "fatter" | "neutral" };

export type Bcs = {
  score: number;
  farmer_score: number;
  label: string;
  confidence: number;
  scale: string;
  beta: boolean;
  note: string;
  signals: Signal[];
  warnings: string[];
};

export type Measurements = {
  body_length_cm: number | null;
  body_depth_cm: number | null;
  leg_length_cm: number | null;
  rump_width_cm: number | null;
  hip_width_cm: number | null;
  rib_visibility: number | null;
  depth_ratio: number | null;
  rump_hip_ratio: number | null;
  warnings: string[];
};

export type BreedGuess = { slug: string; name: string; type: "cow" | "buffalo" | null; confidence: number };
export type Breed = {
  breed: string; // slug or "unsure"
  name: string | null;
  type: "cow" | "buffalo" | null;
  confidence: number;
  unsure: boolean;
  threshold: number;
  top: BreedGuess[];
};

export type AnalyzeResponse = {
  analysis_id: string | null;
  expires_in_seconds: number;
  views: Partial<Record<View, ViewResult>>;
  measurements: Measurements | null;
  bcs: Bcs | null;
  breed: Breed | null;
  warnings: string[];
  models: Record<string, unknown>;
  timing_ms: number;
};

export type RecomputeRequest = {
  analysis_id?: string | null;
  points: Partial<Record<View, Points>>;
  scales?: Partial<Record<View, number | null>>;
  rib_visibility?: number | null;
};
export type RecomputeResponse = { measurements: Measurements; bcs: Bcs | null; rib_source: "photo" | "given" | "none"; warnings: string[] };

export type Animal = {
  id: string;
  owner_id: string;
  species: "cow" | "buffalo";
  name: string | null;
  tag_id: string | null;
  breed_slug: string | null;
  sex: "female" | "male" | "unknown";
  birth_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};
export type AnimalInput = Partial<Omit<Animal, "id" | "owner_id" | "created_at" | "updated_at">> & { species?: "cow" | "buffalo" };

export type AnalysisSummary = {
  id: string;
  created_at: string;
  animal_id: string | null;
  bcs_score: number | null;
  bcs_confidence: number | null;
  breed_slug: string | null;
  breed_confidence: number | null;
  breed_unsure: boolean | null;
  measurements: Measurements | null;
  photo_consent: boolean;
};
export type AnalysisDetail = AnalysisSummary & {
  photos: Partial<Record<View, string>>;
  photo_urls: Partial<Record<View, string>>;
  points: Partial<Record<View, Points>>;
  bcs: Bcs | null;
  breed: Breed | null;
  model_versions: Record<string, unknown>;
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

export const apiBase = () => (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function token(): Promise<string | null> {
  const supabase = getSupabase();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function request<T>(path: string, init: RequestInit & { auth?: boolean } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.auth) {
    const t = await token();
    if (!t) throw new ApiError(401, "not_signed_in", "Sign in to continue.");
    headers.set("Authorization", `Bearer ${t}`);
  }
  let res: Response;
  try {
    res = await fetch(`${apiBase()}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network", "Can't reach the analysis service. Check your connection and try again.");
  }
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    const b = (body ?? {}) as { error?: string; message?: string; detail?: unknown };
    const message = b.message ?? (typeof b.detail === "string" ? b.detail : `Request failed (${res.status})`);
    throw new ApiError(res.status, b.error ?? "http_error", message, body);
  }
  return body as T;
}

const json = (data: unknown): RequestInit => ({
  body: JSON.stringify(data),
  headers: { "Content-Type": "application/json" },
});

export const api = {
  health: () => request<{ status: string; version: string; models: Record<string, unknown> }>("/health"),

  analyze(photos: Partial<Record<View, Blob>>, opts: { markerCm?: number; facing?: "auto" | "left" | "right" } = {}) {
    const form = new FormData();
    for (const [view, blob] of Object.entries(photos)) if (blob) form.append(view, blob, `${view}.jpg`);
    form.append("marker_cm", String(opts.markerCm ?? 20));
    form.append("facing", opts.facing ?? "auto");
    return request<AnalyzeResponse>("/analyze", { method: "POST", body: form });
  },

  recompute: (body: RecomputeRequest) => request<RecomputeResponse>("/recompute", { method: "POST", ...json(body) }),

  listAnimals: () => request<Animal[]>("/animals", { auth: true }),
  getAnimal: (id: string) => request<Animal>(`/animals/${id}`, { auth: true }),
  createAnimal: (a: AnimalInput) => request<Animal>("/animals", { method: "POST", auth: true, ...json(a) }),
  updateAnimal: (id: string, a: AnimalInput) => request<Animal>(`/animals/${id}`, { method: "PATCH", auth: true, ...json(a) }),
  animalHistory: (id: string) => request<AnalysisSummary[]>(`/animals/${id}/analyses`, { auth: true }),

  saveAnalysis(data: RecomputeRequest & { animal_id?: string | null; photo_consent: boolean; breed?: Partial<Breed> | null },
               photos: Partial<Record<View, Blob>> = {}) {
    const form = new FormData();
    form.append("data", JSON.stringify(data));
    if (data.photo_consent) for (const [view, blob] of Object.entries(photos)) if (blob) form.append(view, blob, `${view}.jpg`);
    return request<{ analysis: AnalysisDetail; warnings: string[] }>("/analyses", { method: "POST", auth: true, body: form });
  },
  listAnalyses: () => request<AnalysisSummary[]>("/analyses", { auth: true }),
  getAnalysis: (id: string) => request<AnalysisDetail>(`/analyses/${id}`, { auth: true }),
};
