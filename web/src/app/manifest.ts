import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Gopalan AI",
    short_name: "Gopalan AI",
    description: "Body condition, breed, feeding plans and reminders for cattle and buffalo.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f1e7",
    theme_color: "#2f5d3a",
    lang: "en",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
