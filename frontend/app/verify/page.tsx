"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import LanguageSwitcher from "../../components/LanguageSwitcher";
import { useI18n } from "../../lib/i18n";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

type State = "pending" | "ok" | "error" | "missing";

export default function VerifyPage() {
  const { t } = useI18n();
  const [state, setState] = useState<State>("pending");
  const [email, setEmail] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setState("missing");
      return;
    }
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/verify?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          setState("error");
          return;
        }
        const body = (await res.json()) as { email?: string };
        setEmail(body.email ?? "");
        setState("ok");
      } catch {
        setState("error");
      }
    })();
  }, []);

  const ok = state === "ok";
  const failed = state === "error" || state === "missing";

  return (
    <main id="main" className="flex min-h-[100dvh] flex-col bg-white font-sans text-zinc-900 antialiased">
      <header className="border-b border-black/5">
        <div className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 text-sm font-bold text-white">
              NB
            </span>
            {t("common.app_name")}
          </Link>
          <LanguageSwitcher />
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-6 py-16">
        <div className="w-full rounded-3xl border border-zinc-200/80 bg-white p-7 text-center shadow-sm">
          {state === "pending" && <p className="text-sm text-zinc-500">{t("common.loading")}</p>}

          {ok && (
            <>
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-2xl">
                ✓
              </div>
              <h1 className="mt-4 text-lg font-semibold">{t("auth.verify_success_title")}</h1>
              <p className="mt-2 text-sm text-zinc-500">
                {t("auth.verify_success_body")}
                {email ? ` (${email})` : ""}
              </p>
              <Link
                href="/studio"
                className="mt-6 inline-block w-full rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white"
              >
                {t("auth.back_to_studio")}
              </Link>
            </>
          )}

          {failed && (
            <>
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-2xl">
                !
              </div>
              <h1 className="mt-4 text-lg font-semibold">{t("auth.verify_fail_title")}</h1>
              <p className="mt-2 text-sm text-zinc-500">{t("auth.verify_fail_body")}</p>
              <Link
                href="/studio"
                className="mt-6 inline-block w-full rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white"
              >
                {t("auth.back_to_studio")}
              </Link>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
