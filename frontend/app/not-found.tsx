"use client";

import Link from "next/link";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { useI18n } from "../lib/i18n";

export default function NotFound() {
  const { t } = useI18n();

  return (
    <main
      id="main"
      className="flex min-h-[100dvh] flex-col bg-white font-sans text-zinc-900 antialiased"
    >
      <header className="border-b border-black/5">
        <div className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-[15px] font-semibold tracking-tight"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 text-sm font-bold text-white">
              NB
            </span>
            {t("common.app_name")}
          </Link>
          <LanguageSwitcher />
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-xl flex-1 flex-col items-start justify-center px-6 py-20">
        <p className="font-mono text-sm tracking-widest text-zinc-400">404</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("notfound.title")}
        </h1>
        <p className="mt-3 max-w-[52ch] text-[15px] leading-relaxed text-zinc-500">
          {t("notfound.body")}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/"
            className="rounded-full bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 active:scale-[0.98]"
          >
            {t("notfound.home")}
          </Link>
          <Link
            href="/studio"
            className="rounded-full border border-zinc-300 px-6 py-2.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 active:scale-[0.98]"
          >
            {t("notfound.studio")}
          </Link>
        </div>
      </div>
    </main>
  );
}
