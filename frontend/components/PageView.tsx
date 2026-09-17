"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

/**
 * Privacy-friendly page-view beacon: no cookies, no personal data — only the
 * path and the referrer host are sent, and the API stores a salted hash.
 * Fails silently so it can never affect the page.
 */
export default function PageView() {
  const pathname = usePathname();

  useEffect(() => {
    if (!pathname || pathname.startsWith("/api") || pathname.startsWith("/_next")) return;
    const token =
      typeof window !== "undefined" ? window.localStorage.getItem("nb_token") : null;
    try {
      void fetch(`${API_BASE}/track`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          path: pathname,
          referrer: typeof document !== "undefined" ? document.referrer || "" : "",
        }),
        keepalive: true,
      }).catch(() => undefined);
    } catch {
      /* ignore */
    }
  }, [pathname]);

  return null;
}
