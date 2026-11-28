"use client";

import { useEffect, useRef, useState } from "react";
import type { Dictionary } from "@/i18n";
import { api, ApiError, type AnalyzeResponse, type Bcs, type Measurements, type Points, type View } from "@/lib/api";
import { preparePhoto, setMarkerSize, useMarkerSize, type PreparedPhoto } from "@/lib/photos";
import { CaptureStep, type CaptureState } from "./capture-step";
import { PointsEditor } from "./points-editor";
import { ResultView } from "./result-view";

type T = Dictionary["analyze"];
type Step = 1 | 2 | 3;

export function AnalyzeFlow({ lang, t }: { lang: string; t: T }) {
  const [step, setStep] = useState<Step>(1);
  const markerCm = useMarkerSize();
  const [captureState, setCapture] = useState<Omit<CaptureState, "markerCm">>({ species: "cow", photos: {} });
  const capture: CaptureState = { ...captureState, markerCm };
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [points, setPoints] = useState<Points>({});
  const [live, setLive] = useState<{ bcs: Bcs | null; measurements: Measurements | null; warnings: string[] } | null>(null);
  const [updating, setUpdating] = useState(false);
  const recomputeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestId = useRef(0);
  const top = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Block body on purpose: newer browsers return a Promise from scrollIntoView,
    // and React would try to call it as the effect's cleanup.
    top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [step]);

  async function pick(view: View, file: File) {
    setError(null);
    const prepared = await preparePhoto(file);
    setCapture((c) => {
      const old = c.photos[view];
      if (old) URL.revokeObjectURL(old.url);
      return { ...c, photos: { ...c.photos, [view]: prepared } };
    });
  }

  function remove(view: View) {
    setCapture((c) => {
      const old = c.photos[view];
      if (old) URL.revokeObjectURL(old.url);
      const photos = { ...c.photos };
      delete photos[view];
      return { ...c, photos };
    });
  }

  async function analyze() {
    if (!capture.photos.side) return setError(t.needSide);
    setBusy(true);
    setError(null);
    try {
      const blobs = Object.fromEntries(Object.entries(capture.photos).map(([v, p]) => [v, (p as PreparedPhoto).blob]));
      const res = await api.analyze(blobs, { markerCm: capture.markerCm, species: capture.species });
      const side = res.views.side;
      if (!side?.animal || !Object.keys(side.points).length) {
        setError(`${t.noAnimalTitle}. ${t.noAnimalText}`);
        return;
      }
      setResult(res);
      setPoints(side.points);
      setLive({ bcs: res.bcs, measurements: res.measurements, warnings: [] });
      setStep(2);
    } catch (e) {
      setError(e instanceof ApiError && (e.status === 0 || e.status === 503) ? t.errorService : e instanceof ApiError ? e.message : t.errorGeneric);
    } finally {
      setBusy(false);
    }
  }

  function changePoints(next: Points) {
    setPoints(next);
    if (!result) return;
    if (recomputeTimer.current) clearTimeout(recomputeTimer.current);
    recomputeTimer.current = setTimeout(async () => {
      const id = ++requestId.current;
      setUpdating(true);
      try {
        const scales = Object.fromEntries(
          Object.entries(result.views).map(([v, r]) => [v, r?.marker?.cm_per_px ?? null]),
        );
        const otherViews = Object.fromEntries(
          Object.entries(result.views).filter(([v, r]) => v !== "side" && r && Object.keys(r.points).length).map(([v, r]) => [v, r!.points]),
        );
        const res = await api.recompute({
          analysis_id: result.analysis_id,
          points: { side: next, ...otherViews },
          scales,
          rib_visibility: result.measurements?.rib_visibility ?? null,
        });
        if (id === requestId.current) setLive({ bcs: res.bcs, measurements: res.measurements, warnings: res.warnings });
      } catch {
        /* keep the last good score; the next move retries */
      } finally {
        if (id === requestId.current) setUpdating(false);
      }
    }, 150);
  }

  function restart() {
    Object.values(capture.photos).forEach((p) => p && URL.revokeObjectURL(p.url));
    setCapture((c) => ({ ...c, photos: {} }));
    setResult(null);
    setPoints({});
    setLive(null);
    setError(null);
    setStep(1);
  }

  const side = result?.views.side;
  const warnings = Array.from(new Set([
    ...(side?.warnings ?? []),
    ...(result?.warnings ?? []),
    ...(live?.warnings ?? []),
    ...(live?.bcs?.warnings ?? []),
  ]));
  const stepTitle = { 1: t.stepPhotos, 2: t.stepPoints, 3: t.stepResult }[step];
  const bcs = live?.bcs ?? null;
  const labels = t.labels as Record<string, string>;

  return (
    <div ref={top} className="flex scroll-mt-24 flex-col gap-5">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="text-[14px] font-semibold text-muted">{t.step.replace("{n}", String(step))}</p>
            <h1 className="text-2xl font-extrabold md:text-4xl">{stepTitle}</h1>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-1.5" aria-hidden="true">
          {[1, 2, 3].map((n) => <span key={n} className={`h-1.5 rounded-full ${n <= step ? "bg-forest" : "bg-line"}`} />)}
        </div>
      </div>

      {step === 1 && (
        <CaptureStep
          lang={lang} t={t} state={capture} busy={busy} error={error}
          onChange={({ markerCm: size, ...rest }) => {
            if (size) setMarkerSize(size);
            if (Object.keys(rest).length) setCapture((c) => ({ ...c, ...rest }));
          }}
          onPick={pick} onRemove={remove} onAnalyze={analyze}
        />
      )}

      {step === 2 && side && capture.photos.side && (
        <div className="grid gap-5 md:grid-cols-[1.6fr_1fr] md:items-start md:gap-8">
          <PointsEditor
            imageUrl={capture.photos.side.url}
            width={side.image.width}
            height={side.image.height}
            outline={side.outline}
            points={points}
            t={t}
            onChange={changePoints}
          />
          <div className="flex flex-col gap-4 md:sticky md:top-24">
            <section className="flex items-center justify-between gap-3 rounded-card bg-surface p-5" aria-live="polite">
              <div>
                <div className="text-[14px] text-muted">{t.liveScore}</div>
                <div className="text-3xl font-extrabold tabular-nums">
                  {bcs ? bcs.farmer_score : "–"}{" "}
                  {bcs && <span className="text-lg text-thin">{labels[bcs.label] ?? bcs.label}</span>}
                </div>
              </div>
              <span className="rounded-full bg-soil-soft px-2.5 py-1 text-[13px] font-bold text-soil">{updating ? t.updating : t.beta}</span>
            </section>
            {warnings.length > 0 && (
              <section className="rounded-card bg-[#fff4e5] p-4">
                <h2 className="mb-1 text-[15px] font-bold text-[#5a2e04]">{t.warnings}</h2>
                <ul className="list-disc pl-5 text-[14px] leading-relaxed text-[#5a2e04]">
                  {warnings.map((w) => <li key={w}>{w}</li>)}
                </ul>
              </section>
            )}
            <div className="flex gap-3">
              <button type="button" onClick={restart} className="min-h-14 flex-1 rounded-control border-2 border-line bg-surface text-lg font-bold">{t.retake}</button>
              <button type="button" onClick={() => setStep(3)} className="min-h-14 flex-2 rounded-control bg-forest text-lg font-bold text-white hover:bg-forest-dark">{t.looksGood}</button>
            </div>
          </div>
        </div>
      )}

      {step === 3 && result && (
        <ResultView
          lang={lang} t={t}
          bcs={live?.bcs ?? result.bcs}
          breed={result.breed}
          measurements={live?.measurements ?? result.measurements}
          warnings={warnings}
          onBack={() => setStep(2)}
          onRestart={restart}
        />
      )}
    </div>
  );
}
