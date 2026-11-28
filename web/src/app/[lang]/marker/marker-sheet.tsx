"use client";

import type { Dictionary } from "@/i18n";
import { MARKER_SIZES, setMarkerSize, useMarkerSize, type MarkerSize } from "@/lib/photos";

type T = Dictionary["marker"];

export function MarkerSheet({ t }: { t: T }) {
  const size = useMarkerSize();
  const choose = (s: MarkerSize) => setMarkerSize(s);

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_1.1fr] md:gap-10">
      <div className="flex flex-col gap-5 print:hidden">
        <p className="text-base leading-relaxed text-muted md:text-lg">{t.intro}</p>
        <fieldset className="flex flex-col gap-2.5">
          <legend className="mb-2 text-[17px] font-bold">{t.size}</legend>
          {MARKER_SIZES.map((s) => (
            <label key={s} className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-2xl border-2 px-4 ${size === s ? "border-forest bg-forest-soft" : "border-line bg-surface"}`}>
              <input type="radio" name="size" checked={size === s} onChange={() => choose(s)} className="h-5 w-5 accent-[#2f5d3a]" />
              <span className="text-[16px] font-semibold">{s === 15 ? t.a4 : t.a3}</span>
            </label>
          ))}
        </fieldset>
        <button type="button" onClick={() => window.print()} className="min-h-14 rounded-control bg-forest text-lg font-bold text-white hover:bg-forest-dark">
          {t.print}
        </button>
        <section className="flex flex-col gap-2 rounded-card bg-surface p-5">
          <h2 className="text-[17px] font-bold">{t.tipsTitle}</h2>
          <ol className="list-decimal space-y-1.5 pl-5 text-[15px] leading-relaxed">
            <li>{t.tip1}</li>
            <li>{t.tip2.replace("{size}", String(size))}</li>
            <li>{t.tip3}</li>
            <li>{t.tip4}</li>
          </ol>
        </section>
      </div>

      <div className="flex flex-col items-center gap-3 rounded-card bg-surface p-6 print:rounded-none print:p-0">
        {/* On screen: fits the card. On paper: exactly `size` cm, with a white margin around it. */}
        <div className="w-full max-w-sm bg-white p-[8%] print:w-auto print:max-w-none print:p-[1.5cm]">
          {/* eslint-disable-next-line @next/next/no-img-element -- exact-size print of a static SVG */}
          <img src="/marker/aruco-4x4-50-id0.svg" alt="ArUco marker" className="block w-full print:hidden" />
          {/* eslint-disable-next-line @next/next/no-img-element -- exact-size print of a static SVG */}
          <img src="/marker/aruco-4x4-50-id0.svg" alt="" aria-hidden="true" className="hidden print:block" style={{ width: `${size}cm`, height: `${size}cm` }} />
        </div>
        <p className="text-center text-[13px] text-muted">ArUco DICT_4X4_50 · ID 0 · {size} cm</p>
      </div>
    </div>
  );
}
