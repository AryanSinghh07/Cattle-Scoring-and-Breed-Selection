"use client";

import Link from "next/link";
import { useId, useRef } from "react";
import { CameraIcon, CheckIcon, CowIcon } from "@/components/icons";
import type { Dictionary } from "@/i18n";
import type { View } from "@/lib/api";
import { MARKER_SIZES, type MarkerSize, type PreparedPhoto } from "@/lib/photos";

type T = Dictionary["analyze"];

export type CaptureState = {
  species: "cow" | "buffalo";
  markerCm: MarkerSize;
  photos: Partial<Record<View, PreparedPhoto>>;
};

function PhotoSlot({ view, photo, label, note, hint, t, onPick, onRemove, large }: {
  view: View; photo?: PreparedPhoto; label: string; note: string; hint?: string; t: T; large?: boolean;
  onPick: (view: View, file: File) => void; onRemove: (view: View) => void;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const picker = (
    <input
      ref={input}
      id={id}
      type="file"
      accept="image/*"
      capture="environment"
      className="sr-only"
      onChange={(e) => {
        const f = e.target.files?.[0];
        if (f) onPick(view, f);
        e.target.value = "";
      }}
    />
  );

  if (!photo) {
    return (
      <label
        htmlFor={id}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-[#c9bc9f] bg-[#fbf8f2] text-center transition hover:border-forest hover:bg-forest-soft ${large ? "min-h-48 p-6" : "min-h-28 p-4"}`}
      >
        {picker}
        <CameraIcon size={large ? 32 : 24} className="text-forest" />
        <span className="text-[16px] font-bold">{label}</span>
        <span className="text-[13px] text-muted">{note}</span>
        {hint && <span className="mt-1 text-[13px] text-muted">{hint}</span>}
      </label>
    );
  }

  return (
    <div className={`overflow-hidden rounded-2xl bg-surface ${large ? "border-2 border-forest" : "border border-line"}`}>
      {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
      <img src={photo.url} alt={label} className={`block w-full object-cover ${large ? "h-56 md:h-72" : "h-32"}`} />
      <div className="flex items-center gap-2.5 p-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-forest text-white">
          <CheckIcon size={16} />
        </span>
        <span className="flex-1 text-[15px] font-bold">{label}</span>
        <label htmlFor={id} className="flex min-h-11 cursor-pointer items-center rounded-xl border border-line px-3 text-[15px] font-semibold">
          {picker}
          {t.retake}
        </label>
        {view !== "side" && (
          <button type="button" onClick={() => onRemove(view)} className="min-h-11 rounded-xl px-2 text-[15px] font-semibold text-muted">
            {t.remove}
          </button>
        )}
      </div>
    </div>
  );
}

export function CaptureStep({ lang, t, state, busy, error, onChange, onPick, onRemove, onAnalyze }: {
  lang: string; t: T; state: CaptureState; busy: boolean; error: string | null;
  onChange: (s: Partial<CaptureState>) => void;
  onPick: (view: View, file: File) => void; onRemove: (view: View) => void; onAnalyze: () => void;
}) {
  const choice = (active: boolean) =>
    `flex min-h-16 items-center justify-center gap-2.5 rounded-2xl border-2 text-[17px] font-bold transition ${
      active ? "border-forest bg-forest-soft text-forest-dark" : "border-line bg-surface text-ink hover:border-forest"
    }`;

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_1.2fr] md:gap-10">
      <div className="flex flex-col gap-5">
        <section className="flex flex-col gap-2.5">
          <h2 className="text-[17px] font-bold">{t.whichAnimal}</h2>
          <div className="grid grid-cols-2 gap-2.5" role="group" aria-label={t.whichAnimal}>
            {(["cow", "buffalo"] as const).map((s) => (
              <button key={s} type="button" aria-pressed={state.species === s} onClick={() => onChange({ species: s })} className={choice(state.species === s)}>
                <CowIcon size={26} />
                {s === "cow" ? t.cow : t.buffalo}
              </button>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-3 rounded-card bg-surface p-4 md:p-5">
          <div className="flex items-start gap-3.5">
            {/* eslint-disable-next-line @next/next/no-img-element -- tiny static SVG */}
            <img src="/marker/aruco-4x4-50-id0.svg" alt="" className="h-16 w-16 shrink-0 border-[6px] border-white outline outline-1 outline-line" />
            <div className="flex flex-col gap-1">
              <h2 className="text-[16px] font-bold">{t.markerTitle.replace("{size}", String(state.markerCm))}</h2>
              <p className="text-[14px] leading-snug text-muted">{t.markerText}</p>
              <Link href={`/${lang}/marker`} className="text-[14px] font-bold text-forest">{t.markerLink}</Link>
            </div>
          </div>
          <div className="flex items-center gap-2" role="group" aria-label={t.markerSize}>
            <span className="text-[14px] font-semibold text-muted">{t.markerSize}:</span>
            {MARKER_SIZES.map((size) => (
              <button
                key={size}
                type="button"
                aria-pressed={state.markerCm === size}
                onClick={() => onChange({ markerCm: size })}
                className={`min-h-10 rounded-full px-4 text-[15px] font-bold ${state.markerCm === size ? "bg-forest text-white" : "border border-line bg-surface"}`}
              >
                {size} cm
              </button>
            ))}
          </div>
        </section>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-[17px] font-bold">{t.photos}</h2>
        <PhotoSlot large view="side" photo={state.photos.side} label={t.side} note={t.required} hint={t.sideHint} t={t} onPick={onPick} onRemove={onRemove} />
        <div className="grid grid-cols-2 gap-3">
          <PhotoSlot view="top" photo={state.photos.top} label={t.top} note={t.optional} t={t} onPick={onPick} onRemove={onRemove} />
          <PhotoSlot view="back" photo={state.photos.back} label={t.back} note={t.optional} t={t} onPick={onPick} onRemove={onRemove} />
        </div>
        <p className="text-[14px] text-muted">{t.extraHint}</p>

        {error && <p role="alert" className="rounded-xl bg-thin-soft px-3 py-2.5 text-[15px] text-thin">{error}</p>}

        <button
          type="button"
          onClick={onAnalyze}
          disabled={busy || !state.photos.side}
          className="mt-1 flex min-h-14 items-center justify-center gap-2.5 rounded-control bg-forest px-6 text-lg font-bold text-white transition hover:bg-forest-dark disabled:opacity-60"
        >
          {busy ? (
            <>
              <span aria-hidden="true" className="h-5 w-5 animate-spin rounded-full border-[3px] border-white/40 border-t-white" />
              {t.analyzing}
            </>
          ) : (
            t.analyzeBtn
          )}
        </button>
      </section>
    </div>
  );
}
