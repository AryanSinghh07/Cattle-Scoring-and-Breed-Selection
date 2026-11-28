"use client";

import Link from "next/link";
import { useState } from "react";
import type { Dictionary } from "@/i18n";
import type { Bcs, Breed, Measurements } from "@/lib/api";

type T = Dictionary["analyze"];
type Label = "Very thin" | "Thin" | "Ideal" | "Fat" | "Obese";

const SCALE_COLOURS = ["#c2410c", "#f59e0b", "#4d8b3f", "#8fb36b", "#a8a29e"];
const LABEL_COLOUR: Record<Label, string> = {
  "Very thin": "text-[#9a3412]", Thin: "text-thin", Ideal: "text-forest", Fat: "text-[#4d6b2a]", Obese: "text-[#57534e]",
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[#efe8da] py-2 text-[15px] last:border-0">
      <span className="text-muted">{label}</span>
      <span className="text-right font-bold">{value}</span>
    </div>
  );
}

export function ResultView({ lang, t, bcs, breed, measurements, warnings, onBack, onRestart }: {
  lang: string; t: T; bcs: Bcs | null; breed: Breed | null; measurements: Measurements | null; warnings: string[];
  onBack: () => void; onRestart: () => void;
}) {
  const [view, setView] = useState<"farmer" | "expert">("farmer");
  const [pickedBreed, setPickedBreed] = useState<string | null>(null);
  const expert = view === "expert";
  const label = (bcs?.label ?? "Ideal") as Label;
  const shown = bcs ? (expert ? bcs.score : bcs.farmer_score) : null;
  const labels = t.labels as Record<Label, string>;
  const advice = t.advice as Record<Label, string>;
  const effect = t.effect as Record<string, string>;
  const signalName = (n: string) => ({ depth_ratio: t.depthRatio, rib_visibility: t.ribVisibility, rump_hip_ratio: t.rumpHip }[n] ?? n);
  const cm = (v: number | null | undefined) => (v == null ? t.needsMarker : `${v.toFixed(0)} cm`);
  const hasCm = measurements?.body_length_cm != null;

  const toggle = (v: "farmer" | "expert", text: string) => (
    <button type="button" aria-pressed={view === v} onClick={() => setView(v)}
      className={`min-h-10 rounded-full px-4 text-[14px] font-bold ${view === v ? "bg-forest text-white" : "text-ink"}`}>{text}</button>
  );

  return (
    <div className="grid gap-5 md:grid-cols-2 md:gap-6">
      <section className="flex flex-col gap-4 rounded-card bg-surface p-5 md:row-span-2 md:p-7">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[17px] font-bold">{t.bodyCondition}</h2>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-soil-soft px-2.5 py-0.5 text-[13px] font-bold text-soil">{t.beta}</span>
            <div className="flex rounded-full bg-[#e9e1d1] p-[3px]" role="group">{toggle("farmer", t.farmer)}{toggle("expert", t.expert)}</div>
          </div>
        </div>

        {bcs && shown != null ? (
          <>
            <div className="flex items-baseline gap-3">
              <span className="text-6xl font-extrabold leading-none tabular-nums">{shown}</span>
              <span className={`text-2xl font-extrabold ${LABEL_COLOUR[label]}`}>{labels[label]}</span>
            </div>
            <div className="relative pt-4" aria-hidden="true">
              <div className="grid h-3 grid-cols-5 gap-[3px] overflow-hidden rounded-full">
                {SCALE_COLOURS.map((c) => <span key={c} style={{ background: c }} />)}
              </div>
              <span
                className="absolute top-0 h-0 w-0 -translate-x-1/2 border-x-[8px] border-t-[12px] border-x-transparent border-t-ink transition-all"
                style={{ left: `${((shown - 1) / 4) * 100}%` }}
              />
              <div className="mt-1.5 grid grid-cols-5 text-center text-[12px] text-muted">
                {(t.scale as string[]).map((s) => <span key={s}>{s}</span>)}
              </div>
            </div>
            {expert ? (
              <div className="flex flex-col">
                <Row label={t.score025} value={bcs.score} />
                <Row label={t.confidence} value={`${Math.round(bcs.confidence * 100)}%`} />
                {bcs.signals.map((s) => (
                  <Row key={s.name} label={`${signalName(s.name)} ${s.value}`}
                    value={<span className={s.effect === "thinner" ? "text-thin" : s.effect === "fatter" ? "text-[#4d6b2a]" : ""}>{effect[s.effect]}</span>} />
                ))}
                <p className="pt-2 text-[13px] text-muted">{t.notCalibrated}</p>
              </div>
            ) : (
              <p className="text-[16px] leading-relaxed">{advice[label]}</p>
            )}
          </>
        ) : (
          <p className="text-muted">{t.errorGeneric}</p>
        )}
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-surface p-5 md:p-6">
        <h2 className="text-[17px] font-bold">{t.breed}</h2>
        {!breed ? (
          <p className="text-[15px] text-muted">{t.breedUnavailable}</p>
        ) : (
          <>
            {!breed.unsure && !pickedBreed && (
              <p className="text-xl font-extrabold">{t.breedSure.replace("{name}", breed.name ?? "").replace("{pct}", String(Math.round(breed.confidence * 100)))}</p>
            )}
            <p className="text-[15px] text-muted">{breed.unsure ? t.breedUnsure : t.breedNotRight}</p>
            <div className="flex flex-wrap gap-2" role="group" aria-label={t.breed}>
              {[...breed.top.map((g) => ({ slug: g.slug, name: g.name })), { slug: "unknown", name: t.dontKnow }].map((g) => {
                const on = pickedBreed === g.slug;
                return (
                  <button key={g.slug} type="button" aria-pressed={on} onClick={() => setPickedBreed(g.slug)}
                    className={`min-h-11 rounded-full border-2 px-4 text-[15px] font-bold ${on ? "border-forest bg-forest-soft text-forest-dark" : "border-line bg-surface"}`}>
                    {g.name}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </section>

      <section className="flex flex-col gap-1 rounded-card bg-surface p-5 md:p-6">
        <h2 className="mb-1 text-[17px] font-bold">{t.measurements}</h2>
        <Row label={t.bodyLength} value={cm(measurements?.body_length_cm)} />
        <Row label={t.bodyDepth} value={cm(measurements?.body_depth_cm)} />
        {hasCm && <Row label={t.legLength} value={cm(measurements?.leg_length_cm)} />}
        {measurements?.rump_width_cm != null && <Row label={t.rumpWidth} value={cm(measurements.rump_width_cm)} />}
        {measurements?.hip_width_cm != null && <Row label={t.hipWidth} value={cm(measurements.hip_width_cm)} />}
        {measurements?.depth_ratio != null && <Row label={t.depthRatio} value={measurements.depth_ratio} />}
        {!hasCm && <button type="button" onClick={onRestart} className="mt-2 self-start text-left text-[15px] font-bold text-forest">{t.retakeWithMarker}</button>}
      </section>

      {warnings.length > 0 && (
        <section className="rounded-card bg-[#fff4e5] p-5 md:col-span-2">
          <h2 className="mb-2 text-[15px] font-bold text-[#5a2e04]">{t.warnings}</h2>
          <ul className="list-disc pl-5 text-[14px] leading-relaxed text-[#5a2e04]">
            {warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </section>
      )}

      <div className="flex flex-col gap-3 md:col-span-2 md:flex-row">
        <button type="button" onClick={onRestart} className="min-h-14 flex-1 rounded-control bg-forest px-6 text-lg font-bold text-white hover:bg-forest-dark">{t.analyzeAnother}</button>
        <button type="button" onClick={onBack} className="min-h-14 flex-1 rounded-control border-2 border-line bg-surface px-6 text-lg font-bold">{t.backToPoints}</button>
        <Link href={`/${lang}/help`} className="flex min-h-14 flex-1 items-center justify-center rounded-control border-2 border-line bg-surface px-6 text-lg font-semibold text-ink no-underline">{t.wrongScore}</Link>
      </div>
      <p className="text-[14px] text-muted md:col-span-2">{t.saveSoon}</p>
    </div>
  );
}
