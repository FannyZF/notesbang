"use client";

import { useCallback, useEffect, useState } from "react";
import LanguageSwitcher from "../../components/LanguageSwitcher";
import { useI18n } from "../../lib/i18n";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";
const MAX_CHARS = 3000;

type Platform = { key: string; label: string };
type Evidence = { quote: string; location?: string; verified?: boolean };
type Suggestion = { issue: string; fix: string; example: string; location?: string };
type Dimension = {
  key: string;
  label: string;
  band: number;
  score: number;
  weight: number;
  rationale: string;
  evidence: Evidence[];
  suggestions: Suggestion[];
};
type Scorecard = {
  id: number;
  document_id: number;
  platform: string;
  overall_score: number;
  summary: string;
  dimensions: Dimension[];
  top_priorities?: { point: string; impact?: string }[];
  compliance_flags?: { type: string; quote?: string; severity?: string }[];
};
type Doc = {
  id: number;
  title: string;
  platform: string;
  char_count: number;
  language: string;
  consent_improve: boolean;
  created_at: string;
  content?: string;
};

export default function StudioPage() {
  const { t, locale } = useI18n();
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [platform, setPlatform] = useState("auto");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [consent, setConsent] = useState(true);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [current, setCurrent] = useState<Doc | null>(null);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [rewrite, setRewrite] = useState<{ kind: string; content: string } | null>(null);

  const req = useCallback(
    async (path: string, init?: RequestInit) => {
      const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
          ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...init?.headers,
        },
      });
      let body: unknown = null;
      try {
        body = await res.json();
      } catch {
        /* empty */
      }
      if (!res.ok) {
        const err = new Error(((body as { detail?: string })?.detail) ?? `HTTP ${res.status}`) as Error & {
          code?: string;
        };
        err.code = res.headers.get("X-Error-Code") ?? undefined;
        throw err;
      }
      return body;
    },
    [token]
  );

  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem("nb_token") : null;
    if (stored) setToken(stored);
  }, []);

  const refreshDocs = useCallback(async () => {
    if (!token) return;
    try {
      const list = (await req("/documents")) as Doc[];
      setDocs(list);
    } catch {
      /* ignore */
    }
  }, [req, token]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const [plats] = (await Promise.all([
          req(`/documents/platforms?lang=${locale}`),
          refreshDocs(),
        ])) as [Platform[], void];
        setPlatforms(plats);
      } catch (err) {
        setNotice({ kind: "err", text: errMessage(err) });
      }
    })();
  }, [token, locale, req, refreshDocs]);

  const doAuth = async () => {
    setBusy(true);
    setNotice(null);
    try {
      if (authMode === "register") {
        const r = (await req("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        })) as { dev_verify_url: string | null };
        if (r.dev_verify_url) {
          const tok = new URL(r.dev_verify_url).searchParams.get("token");
          if (tok) await req(`/auth/verify?token=${encodeURIComponent(tok)}`);
        }
      }
      const l = (await req("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as { token: string };
      window.localStorage.setItem("nb_token", l.token);
      setToken(l.token);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const logout = () => {
    window.localStorage.removeItem("nb_token");
    setToken(null);
    setDocs([]);
    setCurrent(null);
    setCard(null);
    setRewrite(null);
  };

  const createFromPaste = async () => {
    if (!token) return setNotice({ kind: "err", text: t("studio.required") });
    if (content.trim().length > MAX_CHARS) {
      return setNotice({ kind: "err", text: t("studio.too_long") });
    }
    try {
      const doc = (await req("/documents", {
        method: "POST",
        body: JSON.stringify({ title, content, platform, consent_improve: consent }),
      })) as Doc;
      setCurrent(doc);
      setCard(null);
      setRewrite(null);
      await refreshDocs();
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const uploadFile = async (file: File | null) => {
    if (!file || !token) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const doc = (await req(
        `/documents/upload?platform=${platform}&consent=${consent}`,
        { method: "POST", body: fd }
      )) as Doc;
      setCurrent(doc);
      setCard(null);
      setRewrite(null);
      await refreshDocs();
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const analyze = async () => {
    if (!current) return;
    setBusy(true);
    setNotice(null);
    try {
      const c = (await req(`/documents/${current.id}/analyze?lang=${locale}`, {
        method: "POST",
      })) as Scorecard;
      setCard(c);
    } catch (err) {
      const e = err as Error & { code?: string };
      setNotice({
        kind: "err",
        text: e.code === "DAILY_LIMIT_REACHED" ? t("studio.limit_reached") : errMessage(err),
      });
    } finally {
      setBusy(false);
    }
  };

  const openDoc = async (id: number) => {
    try {
      const doc = (await req(`/documents/${id}`)) as Doc;
      setCurrent(doc);
      setRewrite(null);
      setCard(null);
      try {
        setCard((await req(`/documents/${id}/analysis`)) as Scorecard);
      } catch {
        /* not analyzed yet */
      }
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const doRewrite = async (kind: "full" | "title" | "hook") => {
    if (!current) return;
    setBusy(true);
    setNotice(null);
    try {
      const r = (await req(`/documents/${current.id}/rewrite?lang=${locale}`, {
        method: "POST",
        body: JSON.stringify({ kind }),
      })) as { kind: string; content: string };
      setRewrite(r);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const exportDoc = async (fmt: "md" | "docx" | "txt") => {
    if (!current) return;
    try {
      const res = await fetch(`${API_BASE}/documents/${current.id}/export?fmt=${fmt}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `notesbang_report.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const chars = content.trim().length;

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-10 font-sans">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("common.app_name")} · Studio</h1>
          <p className="text-sm text-zinc-500">{t("studio.tagline")}</p>
          <p className="text-xs text-zinc-400">{t("studio.free_quota")}</p>
        </div>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          {token && (
            <button onClick={logout} className="rounded-full border border-zinc-200 px-4 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50">
              {t("common.logout")}
            </button>
          )}
        </div>
      </header>

      {notice && (
        <div className={`rounded-2xl border px-4 py-3 text-sm ${notice.kind === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-700"}`}>
          {notice.text}
        </div>
      )}

      {!token ? (
        <section className="mx-auto w-full max-w-md rounded-3xl border border-zinc-200/80 bg-white p-6 shadow-sm">
          <div className="flex rounded-full bg-zinc-100 p-1 text-sm font-medium">
            {(["login", "register"] as const).map((m) => (
              <button key={m} onClick={() => setAuthMode(m)} className={`flex-1 rounded-full px-4 py-2 transition ${authMode === m ? "bg-white shadow-sm" : "text-zinc-500"}`}>
                {m === "login" ? t("common.login") : t("common.register")}
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-col gap-3">
            <input className="rounded-xl border border-zinc-200 px-3.5 py-2.5" type="email" placeholder={t("common.email")} value={email} onChange={(e) => setEmail(e.target.value)} />
            <input className="rounded-xl border border-zinc-200 px-3.5 py-2.5" type="password" placeholder={t("common.password")} value={password} onChange={(e) => setPassword(e.target.value)} />
            <button onClick={doAuth} disabled={busy} className="rounded-full bg-zinc-900 px-5 py-3 text-white disabled:opacity-50">
              {authMode === "login" ? t("common.login") : t("common.register")}
            </button>
          </div>
        </section>
      ) : (
        <div className="flex flex-col gap-6">
          {/* Editor */}
          <section className="rounded-3xl border border-zinc-200/80 bg-white p-6">
            <div className="flex flex-wrap items-center gap-3">
              <select className="rounded-xl border border-zinc-200 px-3 py-2 text-sm" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                {platforms.map((p) => (
                  <option key={p.key} value={p.key}>{p.label}</option>
                ))}
              </select>
              <input className="min-w-48 flex-1 rounded-xl border border-zinc-200 px-3 py-2 text-sm" placeholder={t("studio.title_placeholder")} value={title} onChange={(e) => setTitle(e.target.value)} />
              <label className="cursor-pointer rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50">
                {t("studio.upload")}
                <input type="file" accept=".docx,.txt,.md,.markdown" className="hidden" onChange={(e) => uploadFile(e.target.files?.[0] ?? null)} />
              </label>
            </div>
            <textarea
              className="mt-3 w-full rounded-2xl border border-zinc-200 p-4 text-[15px] leading-relaxed"
              rows={10}
              placeholder={t("studio.paste_placeholder")}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
              <span className={`text-xs ${chars > MAX_CHARS ? "text-red-600" : "text-zinc-400"}`}>
                {chars}/{MAX_CHARS} {t("studio.chars")}
              </span>
              <label className="flex items-center gap-2 text-xs text-zinc-500">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                {t("studio.consent")}
              </label>
              <div className="flex gap-2">
                <button onClick={createFromPaste} className="rounded-full border border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
                  {t("studio.new_analysis")}
                </button>
                <button onClick={analyze} disabled={!current || busy} className="rounded-full bg-zinc-900 px-5 py-2 text-sm text-white disabled:opacity-40">
                  {busy ? t("studio.analyzing") : t("studio.analyze")}
                </button>
              </div>
            </div>
          </section>

          {/* Scorecard */}
          {card && (
            <section className="rounded-3xl border border-zinc-200/80 bg-white p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">{t("studio.scorecard")}</h2>
                <span className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white">
                  {t("studio.overall")}: {card.overall_score}/100
                </span>
              </div>
              {card.summary && <p className="mt-3 text-sm text-zinc-600">{card.summary}</p>}
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {card.dimensions.map((d) => (
                  <div key={d.key} className="rounded-2xl border border-zinc-200/80 p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{d.label}</span>
                      <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs text-zinc-600">
                        {t("studio.band")} {d.band}/5 · {d.score}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
                      <div className="h-full rounded-full bg-zinc-800" style={{ width: `${d.score}%` }} />
                    </div>
                    {d.rationale && <p className="mt-3 text-sm text-zinc-600">{d.rationale}</p>}
                    {d.evidence.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-medium text-zinc-400">{t("studio.evidence")}</p>
                        {d.evidence.map((ev, i) => (
                          <blockquote key={i} className="mt-1 rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
                            “{ev.quote}”
                          </blockquote>
                        ))}
                      </div>
                    )}
                    {d.suggestions.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-medium text-zinc-400">{t("studio.suggestions")}</p>
                        <ul className="mt-1 flex flex-col gap-1.5">
                          {d.suggestions.map((s, i) => (
                            <li key={i} className="rounded-lg border border-zinc-100 px-3 py-2 text-xs text-zinc-600">
                              <b>{s.issue}</b> → {s.fix}
                              {s.example && <span className="mt-1 block text-zinc-400">e.g. {s.example}</span>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Rewrite */}
          {current && (
            <section className="rounded-3xl border border-zinc-200/80 bg-white p-6">
              <div className="flex flex-wrap items-center gap-2">
                <button onClick={() => doRewrite("full")} disabled={busy} className="rounded-full bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-40">
                  {t("studio.full_rewrite")}
                </button>
                <button onClick={() => doRewrite("title")} disabled={busy} className="rounded-full border border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
                  {t("studio.title_options")}
                </button>
                <button onClick={() => doRewrite("hook")} disabled={busy} className="rounded-full border border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
                  {t("studio.hook_options")}
                </button>
                <div className="ml-auto flex gap-2">
                  <button onClick={() => exportDoc("md")} className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50">{t("studio.export_md")}</button>
                  <button onClick={() => exportDoc("docx")} className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50">{t("studio.export_docx")}</button>
                  <button onClick={() => exportDoc("txt")} className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50">{t("studio.export_txt")}</button>
                </div>
              </div>
              {rewrite && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-zinc-400">
                    {rewrite.kind === "full" ? t("studio.revised") : rewrite.kind === "title" ? t("studio.title_options") : t("studio.hook_options")}
                  </p>
                  <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl border border-zinc-200 bg-zinc-50/70 p-4 text-sm leading-relaxed text-zinc-700">
                    {formatRewrite(rewrite)}
                  </pre>
                </div>
              )}
            </section>
          )}

          {/* History */}
          <section className="rounded-3xl border border-zinc-200/80 bg-white p-6">
            <h2 className="text-lg font-semibold">{t("studio.history")}</h2>
            {docs.length === 0 && <p className="mt-2 text-sm text-zinc-400">{t("studio.no_docs")}</p>}
            <div className="mt-3 flex flex-col gap-2">
              {docs.map((d) => (
                <button key={d.id} onClick={() => openDoc(d.id)} className="flex items-center justify-between rounded-xl border border-zinc-200/80 px-4 py-2.5 text-left transition hover:bg-zinc-50">
                  <span className="truncate text-sm text-zinc-700">{d.title || "Untitled"}</span>
                  <span className="shrink-0 text-xs text-zinc-400">
                    {d.platform} · {d.char_count} {t("studio.chars")}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function formatRewrite(r: { kind: string; content: string }): string {
  if (r.kind === "full") return r.content;
  try {
    const items = JSON.parse(r.content) as { style: string; text: string }[];
    return items.map((it) => `· [${it.style}] ${it.text}`).join("\n");
  } catch {
    return r.content;
  }
}

function errMessage(err: unknown): string {
  const e = err as Error & { code?: string };
  return e.code ? `${e.code}: ${e.message}` : (e.message ?? "Unknown error");
}
