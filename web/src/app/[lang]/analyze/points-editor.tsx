"use client";

import { useRef, useState } from "react";
import type { Dictionary } from "@/i18n";
import type { Points } from "@/lib/api";

type T = Dictionary["analyze"];

const ORDER = ["nose", "back", "belly", "tail", "knee", "hoof", "rib_top_left", "rib_bottom_right"] as const;
const NEEDS_CHECK = 0.5;

/**
 * Side photo with the animal outline and draggable body points.
 * Coordinates are in original photo pixels (the API's space). A point the
 * user moved gets confidence 1 (it's now confirmed).
 */
export function PointsEditor({ imageUrl, width, height, outline, points, t, onChange }: {
  imageUrl: string;
  width: number;
  height: number;
  outline: [number, number][];
  points: Points;
  t: T;
  onChange: (points: Points) => void;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [selected, setSelected] = useState<string>(() => ORDER.find((k) => (points[k]?.confidence ?? 1) < NEEDS_CHECK) ?? "nose");
  const [dragging, setDragging] = useState<string | null>(null);

  const r = Math.max(width, height) / 70; // point size relative to the photo
  const names = t.points as Record<string, string>;

  function toPhoto(e: React.PointerEvent): { x: number; y: number } | null {
    const el = svg.current;
    const ctm = el?.getScreenCTM();
    if (!el || !ctm) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    return { x: Math.min(width, Math.max(0, p.x)), y: Math.min(height, Math.max(0, p.y)) };
  }

  function move(name: string, x: number, y: number) {
    onChange({ ...points, [name]: { x, y, confidence: 1 } });
  }

  function onKey(name: string, e: React.KeyboardEvent) {
    const step = (e.shiftKey ? 5 : 1) * (width / 200);
    const p = points[name];
    const d: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!p || !d[e.key]) return;
    e.preventDefault();
    move(name, Math.min(width, Math.max(0, p.x + d[e.key][0])), Math.min(height, Math.max(0, p.y + d[e.key][1])));
  }

  const ribA = points.rib_top_left;
  const ribB = points.rib_bottom_right;
  const sel = points[selected];
  const selCheck = (sel?.confidence ?? 1) < NEEDS_CHECK;

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-2xl bg-[#ddd3bf] shadow-[0_8px_24px_rgba(30,42,30,0.12)]">
        <svg
          ref={svg}
          viewBox={`0 0 ${width} ${height}`}
          className="block h-auto w-full select-none"
          role="group"
          aria-label={t.dragHint}
          onPointerMove={(e) => {
            if (!dragging) return;
            const p = toPhoto(e);
            if (p) move(dragging, p.x, p.y);
          }}
          onPointerUp={() => setDragging(null)}
          onPointerCancel={() => setDragging(null)}
        >
          <image href={imageUrl} x={0} y={0} width={width} height={height} />
          {outline.length > 2 && (
            <polygon
              points={outline.map(([x, y]) => `${x},${y}`).join(" ")}
              fill="rgba(47,93,58,0.10)"
              stroke="#2f7d32"
              strokeWidth={r / 4}
              strokeLinejoin="round"
            />
          )}
          {ribA && ribB && (
            <rect
              x={Math.min(ribA.x, ribB.x)}
              y={Math.min(ribA.y, ribB.y)}
              width={Math.abs(ribB.x - ribA.x)}
              height={Math.abs(ribB.y - ribA.y)}
              fill="none"
              stroke="#f59e0b"
              strokeWidth={r / 4}
              strokeDasharray={`${r} ${r / 1.5}`}
            />
          )}
          {ORDER.filter((k) => points[k]).map((name) => {
            const p = points[name];
            const check = p.confidence < NEEDS_CHECK;
            const isSel = name === selected;
            return (
              <g
                key={name}
                role="button"
                tabIndex={0}
                aria-label={`${names[name] ?? name}: ${check ? t.legendCheck : t.legendOk}`}
                aria-pressed={isSel}
                className="cursor-grab outline-none focus-visible:[&>circle:last-child]:stroke-[#1e2a1e]"
                style={{ touchAction: "none" }}
                onPointerDown={(e) => {
                  e.preventDefault();
                  (e.target as Element).setPointerCapture?.(e.pointerId);
                  setSelected(name);
                  setDragging(name);
                }}
                onFocus={() => setSelected(name)}
                onKeyDown={(e) => onKey(name, e)}
              >
                {/* large invisible touch target */}
                <circle cx={p.x} cy={p.y} r={r * 2.6} fill="transparent" />
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isSel ? r * 1.35 : r}
                  fill={check ? "#f59e0b" : "#2f7d32"}
                  stroke={isSel ? "#1e2a1e" : "#ffffff"}
                  strokeWidth={r / 2.5}
                />
              </g>
            );
          })}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-[14px] text-muted">
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-2 border-white bg-ok shadow" />{t.legendOk}</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-2 border-white bg-check-dot shadow" />{t.legendCheck}</span>
        <span className="hidden md:inline">· {t.dragHint}</span>
      </div>

      {sel && (
        <div className={`flex items-center gap-3 rounded-2xl p-3.5 ${selCheck ? "bg-thin-soft" : "bg-forest-soft"}`} aria-live="polite">
          <span className={`h-4 w-4 shrink-0 rounded-full border-[3px] border-white shadow ${selCheck ? "bg-check-dot" : "bg-ok"}`} />
          <div className="flex-1">
            <div className="text-[16px] font-bold">{t.selected}: {names[selected] ?? selected}</div>
            <div className="text-[14px] text-muted">{selCheck ? t.checkHint : t.okHint}</div>
          </div>
        </div>
      )}
    </div>
  );
}
