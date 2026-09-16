"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import en from "../messages/en.json";
import zh from "../messages/zh.json";

export type Locale = "en" | "zh";

const DICTS: Record<Locale, Record<string, Record<string, string>>> = {
  en: en as Record<string, Record<string, string>>,
  zh: zh as Record<string, Record<string, string>>,
};

type I18nValue = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nValue | null>(null);

function detectLocale(): Locale {
  if (typeof window === "undefined") return "en";
  const cookie = document.cookie
    .split("; ")
    .find((c) => c.startsWith("nb_locale="));
  if (cookie) {
    const value = cookie.split("=")[1];
    if (value === "zh" || value === "en") return value;
  }
  const langs = navigator.languages || [navigator.language || "en"];
  return langs.some((l) => l.toLowerCase().startsWith("zh")) ? "zh" : "en";
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    setLocaleState(detectLocale());
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    document.cookie = `nb_locale=${l}; path=/; max-age=31536000`;
    document.documentElement.lang = l === "zh" ? "zh-CN" : "en";
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      const [ns, name] = key.includes(".") ? key.split(".") : ["common", key];
      let text = DICTS[locale]?.[ns]?.[name] ?? DICTS.en?.[ns]?.[name] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          text = text.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
        }
      }
      return text;
    },
    [locale]
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within LocaleProvider");
  return ctx;
}
