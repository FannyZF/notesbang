"use client";

import { useI18n } from "../lib/i18n";

export default function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();
  return (
    <div className="flex rounded-full bg-zinc-100 p-0.5 text-xs font-medium">
      {(["zh", "en"] as const).map((l) => (
        <button
          key={l}
          onClick={() => setLocale(l)}
          className={`rounded-full px-2.5 py-1 transition ${
            locale === l ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500 hover:text-zinc-700"
          }`}
        >
          {l === "zh" ? "中文" : "EN"}
        </button>
      ))}
    </div>
  );
}
