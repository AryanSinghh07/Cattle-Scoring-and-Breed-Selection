"use client";

import { useSyncExternalStore } from "react";

export type PreparedPhoto = { blob: Blob; url: string; width: number; height: number };

const MAX_SIDE = 2048;

/**
 * Shrink a phone photo (respecting its EXIF rotation) to at most 2048 px and
 * re-encode it as JPEG. Faster uploads on slow networks; the API needs no more.
 */
export async function preparePhoto(file: File): Promise<PreparedPhoto> {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d")!.drawImage(bitmap, 0, 0, width, height);
    bitmap.close();
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), "image/jpeg", 0.9),
    );
    return { blob, url: URL.createObjectURL(blob), width, height };
  } catch {
    // Formats the browser can't decode (e.g. some HEIC): send as is; the API reports problems.
    return { blob: file, url: URL.createObjectURL(file), width: 0, height: 0 };
  }
}

const MARKER_KEY = "gopalan.markerCm";
export const MARKER_SIZES = [15, 20] as const;
export type MarkerSize = (typeof MARKER_SIZES)[number];

/** Marker size the user printed (15 cm fits A4). Stored on this device only. */
export function getMarkerSize(): MarkerSize {
  try {
    const v = Number(localStorage.getItem(MARKER_KEY));
    return v === 20 ? 20 : 15;
  } catch {
    return 15;
  }
}

const CHANGE_EVENT = "gopalan:marker-size";

export function setMarkerSize(size: MarkerSize) {
  try {
    localStorage.setItem(MARKER_KEY, String(size));
  } catch {
    /* private mode etc.: the choice just isn't remembered */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** The saved marker size, kept in sync across pages and tabs (15 cm on the server). */
export function useMarkerSize(): MarkerSize {
  return useSyncExternalStore(subscribe, getMarkerSize, () => 15);
}
