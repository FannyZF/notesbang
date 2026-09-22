"use client";

import { useCallback, useEffect, useState } from "react";
import LanguageSwitcher from "../../components/LanguageSwitcher";
import RadarChart from "../../components/RadarChart";
import { FREE_DAILY_LIMIT, MAX_CONTENT_CHARS } from "../../lib/config";
import { useI18n } from "../../lib/i18n";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";
const MAX_CHARS = MAX_CONTENT_CHARS;
const PALETTE = ["#2563eb", "#db2777", "#16a34a", "#d97706", "#7c3aed"];

type Platform = {
  key: string;
  label: string;
  dimensions?: { key: string; label: string; definition?: string }[];
};
type Archetype = { key: string; label: string };
type AuditResult = {
  status?: string;
  audit_results?: Record<string, string>;
  audit_notes?: string;
  issues?: { check?: string; quote?: string; note?: string }[];
};
type ChangelogEntry = {
  change?: string;
  why?: string;
  original?: string;
  revised?: string;
  verified?: boolean;
};
type Evidence = { quote: string; location?: string; verified?: boolean };
type Suggestion = { issue: string; fix: string; example: string; location?: string };
type Viewpoint = { expert: string; label: string; rationale: string; band?: number; score?: number };
type ExpertScorecard = {
  key: string;
  label: string;
  overall: number;
  dimensions: { key: string; band: number; score: number }[];
};
type Dimension = {
  key: string;
  label: string;
  band: number;
  score: number;
  spread?: number;
  weight: number;
  rationale: string;
  evidence: Evidence[];
  suggestions: Suggestion[];
  viewpoints?: Viewpoint[];
};
type DiffSegment = { op: "equal" | "insert" | "delete"; text: string };
type Consensus = {
  summary?: string;
  strengths?: string[];
  weaknesses?: string[];
  top_priorities?: { point: string; impact?: string }[];
  disagreement?: { key: string; note: string }[];
  must_fix?: string[];
};
type Scorecard = {
  id: number;
  document_id: number;
  platform: string;
  overall_score: number;
  summary: string;
  dimensions: Dimension[];
  experts?: ExpertScorecard[];
  consensus?: Consensus;
};
type Doc = {
  id: number;
  title: string;
  platform: string;
  archetype?: string;
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
  const [confirmPassword, setConfirmPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authStep, setAuthStep] = useState<"form" | "verify">("form");
  const [pendingEmail, setPendingEmail] = useState("");
  const [devVerifyUrl, setDevVerifyUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [platform, setPlatform] = useState("auto");
  const [archetypes, setArchetypes] = useState<Archetype[]>([]);
  const [archetype, setArchetype] = useState("auto");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [consent, setConsent] = useState(true);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [current, setCurrent] = useState<Doc | null>(null);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [rewrite, setRewrite] = useState<{
    kind: string;
    content: string;
    meta?: { diff?: DiffSegment[]; changelog?: ChangelogEntry[]; audit?: AuditResult | null };
  } | null>(null);
  const [focus, setFocus] = useState<string[]>([]);
  const [showDiff, setShowDiff] = useState(false);
  const [jobPhase, setJobPhase] = useState("");
  const [jobProgress, setJobProgress] = useState(0);
  const [adopt, setAdopt] = useState<string[]>([]);
  const [quota, setQuota] = useState<{ limit: number; used: number; remaining: number } | null>(null);
  const [quotaOpen, setQuotaOpen] = useState(false);

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
        const [plats, q] = (await Promise.all([
          req(`/documents/platforms?lang=${locale}`),
          req("/documents/quota"),
          refreshDocs(),
        ])) as [
          { platforms: Platform[]; archetypes: Archetype[] },
          { limit: number; used: number; remaining: number },
          void,
        ];
        setPlatforms(plats.platforms);
        setArchetypes(plats.archetypes ?? []);
        setQuota(q);
      } catch (err) {
        setNotice({ kind: "err", text: errMessage(err) });
      }
    })();
  }, [token, locale, req, refreshDocs]);

  const localizeAuthError = (err: unknown) => {
    const e = err as Error & { code?: string };
    if (e.code === "EMAIL_NOT_VERIFIED") return t("auth.err_not_verified");
    const d = e.message ?? "";
    if (/already registered/i.test(d)) return t("auth.err_email_taken");
    if (/invalid credentials/i.test(d)) return t("auth.err_bad_credentials");
    if (/rate/i.test(d)) return t("auth.err_rate");
    if (/password/i.test(d) && /8|short|least/i.test(d)) return t("auth.err_weak_password");
    return d;
  };

  const doAuth = async () => {
    setBusy(true);
    setNotice(null);
    try {
      if (authMode === "register") {
        if (password !== confirmPassword) {
          setNotice({ kind: "err", text: t("auth.err_password_mismatch") });
          return;
        }
        const r = (await req("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        })) as { dev_verify_url: string | null };
        setPendingEmail(email);
        setDevVerifyUrl(r.dev_verify_url ?? null);
        setAuthStep("verify");
        setNotice({ kind: "ok", text: t("auth.verify_sent", { email }) });
        return;
      }
      const l = (await req("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as { token: string };
      window.localStorage.setItem("nb_token", l.token);
      setToken(l.token);
    } catch (err) {
      const code = (err as Error & { code?: string }).code;
      if (code === "EMAIL_NOT_VERIFIED") {
        setPendingEmail(email);
        setDevVerifyUrl(null);
        setAuthStep("verify");
      }
      setNotice({ kind: "err", text: localizeAuthError(err) });
    } finally {
      setBusy(false);
    }
  };

  const resendVerification = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const r = (await req("/auth/resend-verification-email", {
        method: "POST",
        body: JSON.stringify({ email: pendingEmail || email }),
      })) as { dev_verify_url: string | null };
      setDevVerifyUrl(r.dev_verify_url ?? null);
      setNotice({ kind: "ok", text: t("auth.resent") });
    } catch (err) {
      setNotice({ kind: "err", text: localizeAuthError(err) });
    } finally {
      setBusy(false);
    }
  };

  const openDevVerify = () => {
    if (!devVerifyUrl) return;
    try {
      const tok = new URL(devVerifyUrl).searchParams.get("token");
      window.location.href = tok ? `/verify?token=${encodeURIComponent(tok)}` : devVerifyUrl;
    } catch {
      window.location.href = devVerifyUrl;
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
        body: JSON.stringify({ title, content, platform, archetype, consent_improve: consent }),
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
        `/documents/upload?platform=${platform}&archetype=${archetype}&consent=${consent}`,
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

  const stageLabel = (phase: string) => {
    if (/read/i.test(phase)) return t("studio.stage_reading");
    if (/committee/i.test(phase)) return t("studio.stage_committee");
    if (/scor|consensus/i.test(phase)) return t("studio.stage_scoring");
    if (/writ|suggest/i.test(phase)) return t("studio.stage_writing");
    return phase || t("studio.analyzing");
  };

  const analyze = async () => {
    if (!current) return;
    if (quota && quota.remaining <= 0) {
      setQuotaOpen(true);
      return;
    }
    setBusy(true);
    setNotice(null);
    setCard(null);
    setRewrite(null);
    setJobPhase(t("studio.stage_reading"));
    setJobProgress(2);
    try {
      const start = (await req(
        `/documents/${current.id}/analyze?lang=${locale}&focus=${focus.join(",")}&archetype=${archetype}`,
        { method: "POST" }
      )) as { job_id: number };
      const deadline = Date.now() + 5 * 60 * 1000;
      let status = "queued";
      while (Date.now() < deadline) {
        const job = (await req(`/jobs/${start.job_id}`)) as {
          status: string;
          phase: string;
          progress: number;
          error: string | null;
        };
        setJobProgress(job.progress);
        if (job.phase) setJobPhase(job.phase);
        status = job.status;
        if (status === "succeeded") break;
        if (status === "failed") throw new Error(job.error || "Analysis failed");
        await new Promise((r) => setTimeout(r, 800));
      }
      if (status !== "succeeded") throw new Error("Timed out");
      const c = (await req(`/documents/${current.id}/analysis?lang=${locale}`)) as Scorecard;
      setCard(c);
      setAdopt((c.experts ?? []).map((e) => e.key));
      req("/documents/quota")
        .then((q) => setQuota(q as { limit: number; used: number; remaining: number }))
        .catch(() => undefined);
    } catch (err) {
      const e = err as Error & { code?: string };
      if (e.code === "DAILY_LIMIT_REACHED") {
        setQuotaOpen(true);
      } else {
        setNotice({ kind: "err", text: errMessage(err) });
      }
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

  const deleteDoc = async (id: number) => {
    if (!window.confirm(t("studio.delete_confirm"))) return;
    try {
      await req(`/documents/${id}`, { method: "DELETE" });
      setDocs((prev) => prev.filter((d) => d.id !== id));
      if (current?.id === id) {
        setCurrent(null);
        setCard(null);
        setRewrite(null);
      }
      setNotice({ kind: "ok", text: t("studio.deleted") });
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
        body: JSON.stringify({ kind, adopt }),
      })) as { kind: string; content: string; meta?: { diff?: DiffSegment[] } };
      setRewrite(r);
      setShowDiff(kind === "full" && !!r.meta?.diff);
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
  const dims = platforms.find((p) => p.key === platform)?.dimensions ?? [];
  const highPriorities = (card?.consensus?.top_priorities ?? []).filter(
    (p) => (p.impact ?? "").toLowerCase() === "high"
  );
  const toggleFocus = (key: string) =>
    setFocus((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));

  return (
    <main id="main" className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-10 font-sans">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("common.app_name")} · Studio</h1>
          <p className="text-sm text-zinc-500">{t("studio.tagline")}</p>
          <p className="text-xs text-zinc-400">
            {t("studio.free_quota", { limit: quota?.limit ?? FREE_DAILY_LIMIT })}
          </p>
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
          {authStep === "verify" ? (
            <div className="flex flex-col gap-3 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-2xl">
                ✉
              </div>
              <h1 className="text-lg font-semibold">{t("auth.verify_title")}</h1>
              <p className="text-sm text-zinc-500">
                {t("auth.verify_sent", { email: pendingEmail || email })}
              </p>
              <p className="text-xs text-zinc-400">{t("auth.verify_body")}</p>
              {devVerifyUrl && (
                <button
                  onClick={openDevVerify}
                  className="rounded-full border border-dashed border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-700"
                >
                  {t("auth.dev_open")}
                </button>
              )}
              <button
                onClick={resendVerification}
                disabled={busy}
                className="rounded-full border border-zinc-200 px-4 py-2.5 text-sm text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
              >
                {t("auth.resend")}
              </button>
              <button
                onClick={() => {
                  setAuthStep("form");
                  setAuthMode("login");
                  setNotice(null);
                }}
                className="rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white"
              >
                {t("auth.already_done")}
              </button>
            </div>
          ) : (
            <>
              <div className="text-center">
                <h1 className="text-lg font-semibold">
                  {authMode === "login" ? t("auth.welcome_back") : t("auth.create_title")}
                </h1>
                <p className="mt-1 text-sm text-zinc-500">
                  {authMode === "login" ? t("auth.welcome_back_sub") : t("auth.create_sub")}
                </p>
              </div>
              <div className="mt-4 flex rounded-full bg-zinc-100 p-1 text-sm font-medium">
                {(["login", "register"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => {
                      setAuthMode(m);
                      setNotice(null);
                    }}
                    className={`flex-1 rounded-full px-4 py-2 transition ${authMode === m ? "bg-white shadow-sm" : "text-zinc-500"}`}
                  >
                    {m === "login" ? t("common.login") : t("common.register")}
                  </button>
                ))}
              </div>
              <form
                className="mt-4 flex flex-col gap-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  void doAuth();
                }}
              >
                <input
                  className="rounded-xl border border-zinc-200 px-3.5 py-2.5"
                  type="email"
                  autoComplete="email"
                  placeholder={t("common.email")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <input
                  className="rounded-xl border border-zinc-200 px-3.5 py-2.5"
                  type="password"
                  autoComplete={authMode === "login" ? "current-password" : "new-password"}
                  placeholder={t("common.password")}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                {authMode === "register" && (
                  <>
                    <input
                      className="rounded-xl border border-zinc-200 px-3.5 py-2.5"
                      type="password"
                      autoComplete="new-password"
                      placeholder={t("auth.confirm_password")}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                    <p className="text-xs leading-relaxed text-zinc-400">{t("auth.register_note")}</p>
                  </>
                )}
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-full bg-zinc-900 px-5 py-3 text-white disabled:opacity-50"
                >
                  {authMode === "login" ? t("common.login") : t("common.register")}
                </button>
              </form>
            </>
          )}
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
              {archetypes.length > 0 && (
                <select
                  className="rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-600"
                  value={archetype}
                  onChange={(e) => setArchetype(e.target.value)}
                  title={t("studio.archetype")}
                >
                  {archetypes.map((a) => (
                    <option key={a.key} value={a.key}>{a.label}</option>
                  ))}
                </select>
              )}
              <input className="min-w-48 flex-1 rounded-xl border border-zinc-200 px-3 py-2 text-sm" placeholder={t("studio.title_placeholder")} value={title} onChange={(e) => setTitle(e.target.value)} />
              <label className="cursor-pointer rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50">
                {t("studio.upload")}
                <input type="file" accept=".docx,.txt,.md,.markdown" className="hidden" onChange={(e) => uploadFile(e.target.files?.[0] ?? null)} />
              </label>
            </div>
            {dims.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <span className="text-zinc-400">{t("studio.focus")}:</span>
                {dims.map((d) => (
                  <button
                    key={d.key}
                    title={d.definition}
                    onClick={() => toggleFocus(d.key)}
                    className={`rounded-full px-3 py-1 font-medium transition ${
                      focus.includes(d.key)
                        ? "bg-zinc-900 text-white"
                        : "border border-zinc-200 text-zinc-500 hover:bg-zinc-50"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
                <span className="text-zinc-300">{t("studio.focus_hint")}</span>
              </div>
            )}
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
              <div className="flex items-center gap-3">
                {quota && (
                  <span className="text-xs text-zinc-400">
                    {t("studio.quota_remaining", {
                      remaining: String(quota.remaining),
                      limit: String(quota.limit),
                    })}
                  </span>
                )}
                <button onClick={createFromPaste} className="rounded-full border border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
                  {t("studio.new_analysis")}
                </button>
                <button onClick={analyze} disabled={!current || busy} className="rounded-full bg-zinc-900 px-5 py-2 text-sm text-white disabled:opacity-40">
                  {busy ? t("studio.analyzing") : t("studio.analyze")}
                </button>
              </div>
            </div>
          </section>

          {/* Committee progress */}
          {busy && (
            <section className="rounded-3xl border border-zinc-200/80 bg-white p-6">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-zinc-700">{stageLabel(jobPhase)}</span>
                <span className="text-zinc-400 tnum">{jobProgress}%</span>
              </div>
              <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-zinc-100">
                <div
                  className="h-full rounded-full bg-zinc-900 transition-all duration-500"
                  style={{ width: `${jobProgress}%` }}
                />
              </div>
              <ul className="mt-4 grid gap-1.5 text-xs">
                {[
                  { at: 5, key: "studio.stage_reading" },
                  { at: 30, key: "studio.stage_committee" },
                  { at: 80, key: "studio.stage_scoring" },
                  { at: 90, key: "studio.stage_writing" },
                ].map((s) => {
                  const done = jobProgress >= s.at;
                  const active = !done && jobProgress >= s.at - 30;
                  return (
                    <li key={s.key} className="flex items-center gap-2">
                      <span className={done ? "text-emerald-500" : active ? "animate-pulse text-zinc-900" : "text-zinc-300"}>
                        {done ? "✔" : active ? "●" : "○"}
                      </span>
                      <span className={done || active ? "text-zinc-600" : "text-zinc-300"}>
                        {t(s.key)}
                      </span>
                    </li>
                  );
                })}
              </ul>
              <p className="mt-3 text-xs text-zinc-400">
                {t("studio.experts")} · 5
              </p>
            </section>
          )}

          {/* Skeleton while the committee runs */}
          {busy && !card && (
            <section
              aria-hidden
              className="rounded-3xl border border-zinc-200/80 bg-white p-5 sm:p-6"
            >
              <div className="flex items-center justify-between">
                <div className="h-5 w-32 animate-pulse rounded-full bg-zinc-100" />
                <div className="h-7 w-28 animate-pulse rounded-full bg-zinc-100" />
              </div>
              <div className="mt-5 grid gap-4 lg:grid-cols-3">
                <div className="h-40 animate-pulse rounded-2xl bg-zinc-50" />
                <div className="h-40 animate-pulse rounded-2xl bg-zinc-50" />
                <div className="h-40 animate-pulse rounded-2xl bg-zinc-50" />
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="h-24 animate-pulse rounded-2xl bg-zinc-50" />
                ))}
              </div>
            </section>
          )}

          {/* Scorecard */}
          {card && (
            <section className="rounded-3xl border border-zinc-200/80 bg-white p-5 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">{t("studio.scorecard")}</h2>
                <span className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white tnum">
                  {t("studio.overall")}: {card.overall_score}/100
                </span>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                {/* Left: consensus strengths / weaknesses */}
                {(card.consensus?.strengths?.length ?? 0) > 0 && (
                  <div className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4 lg:col-start-1 lg:row-start-1">
                    <p className="text-xs font-medium text-emerald-700">{t("studio.strengths")}</p>
                    <ul className="mt-2 flex flex-col gap-1 text-sm leading-relaxed text-emerald-900">
                      {card.consensus!.strengths!.map((s, i) => (
                        <li key={i}>· {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {(card.consensus?.weaknesses?.length ?? 0) > 0 && (
                  <div className="rounded-2xl border border-rose-100 bg-rose-50/50 p-4 lg:col-start-1 lg:row-start-2">
                    <p className="text-xs font-medium text-rose-700">{t("studio.weaknesses")}</p>
                    <ul className="mt-2 flex flex-col gap-1 text-sm leading-relaxed text-rose-900">
                      {card.consensus!.weaknesses!.map((w, i) => (
                        <li key={i}>· {w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Center: radar + summary */}
                <div className="rounded-2xl border border-zinc-200/80 p-3 lg:col-start-2 lg:row-start-1">
                  {card.experts && card.experts.length > 0 ? (
                    <>
                      <RadarChart
                        axes={card.dimensions.map((d) => d.label)}
                        series={[
                          ...card.experts.map((e, i) => ({
                            label: e.label,
                            color: PALETTE[i % PALETTE.length],
                            values: card.dimensions.map((d) => {
                              const m = e.dimensions.find((x) => x.key === d.key);
                              return m ? m.score : 0;
                            }),
                          })),
                          {
                            label: t("studio.committee"),
                            color: "#18181b",
                            values: card.dimensions.map((d) => d.score),
                          },
                        ]}
                      />
                      <div className="mt-1 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px] text-zinc-500">
                        {card.experts.map((e, i) => (
                          <span key={e.key} className="flex items-center gap-1">
                            <span
                              className="inline-block h-2 w-2 rounded-full"
                              style={{ background: PALETTE[i % PALETTE.length] }}
                            />
                            {e.label} {e.overall}
                          </span>
                        ))}
                        <span className="flex items-center gap-1 font-medium text-zinc-700">
                          <span className="inline-block h-2 w-2 rounded-full bg-zinc-900" />
                          {t("studio.committee")} {card.overall_score}
                        </span>
                      </div>
                    </>
                  ) : (
                    <p className="p-6 text-center text-xs text-zinc-400">{t("studio.radar")}</p>
                  )}
                </div>
                <div className="rounded-2xl bg-zinc-50/80 p-4 lg:col-start-2 lg:row-start-2">
                  <p className="text-xs font-medium text-zinc-400">
                    {t("studio.consensus_summary")}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-zinc-600">
                    {card.consensus?.summary || card.summary || "-"}
                  </p>
                </div>

                {/* Right: must-fix + high priorities */}
                {(card.consensus?.must_fix?.length ?? 0) > 0 && (
                  <div className="rounded-2xl border border-red-200 bg-red-50 p-4 lg:col-start-3 lg:row-start-1">
                    <p className="text-xs font-medium text-red-700">{t("studio.must_fix")}</p>
                    <ul className="mt-2 flex flex-col gap-1 text-sm font-medium leading-relaxed text-red-800">
                      {card.consensus!.must_fix!.map((m, i) => (
                        <li key={i}>· {m}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {highPriorities.length > 0 && (
                  <div className="rounded-2xl bg-zinc-50/80 p-4 lg:col-start-3 lg:row-start-2">
                    <p className="text-xs font-medium text-zinc-400">
                      {t("studio.priorities")}
                    </p>
                    <ul className="mt-2 flex flex-col gap-1 text-sm leading-relaxed text-zinc-600">
                      {highPriorities.map((p, i) => (
                        <li key={i}>· {p.point}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Dimension score cards */}
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {[...card.dimensions]
                  .sort((a, b) => a.score - b.score)
                  .map((d) => (
                    <div key={d.key} className="rounded-2xl border border-zinc-200/80 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">{d.label}</span>
                        <span className="shrink-0 rounded-full bg-zinc-100 px-2.5 py-1 text-xs text-zinc-600">
                          {t("studio.score")} {d.score}/100 · {t("studio.band")} {d.band}/5 ·{" "}
                          {t("studio.weight")} {Math.round(d.weight * 100)}%
                          {typeof d.spread === "number" && d.spread > 0
                            ? ` · ${t("studio.spread")} ${d.spread}`
                            : ""}
                        </span>
                      </div>
                      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
                        <div
                          className="h-full rounded-full bg-zinc-800"
                          style={{ width: `${d.score}%` }}
                        />
                      </div>
                      {d.rationale && (
                        <p className="mt-3 text-sm leading-relaxed text-zinc-600">{d.rationale}</p>
                      )}
                      <details className="mt-3">
                        <summary className="cursor-pointer text-xs font-medium text-zinc-400 transition hover:text-zinc-600">
                          {t("studio.details")}
                        </summary>
                        {d.evidence.length > 0 && (
                          <div className="mt-2">
                            <p className="text-xs font-medium text-zinc-400">
                              {t("studio.evidence")}
                            </p>
                            {d.evidence.map((ev, i) => (
                              <blockquote
                                key={i}
                                className="mt-1 rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-500"
                              >
                                “{ev.quote}”
                              </blockquote>
                            ))}
                          </div>
                        )}
                        {d.suggestions.length > 0 && (
                          <div className="mt-2">
                            <p className="text-xs font-medium text-zinc-400">
                              {t("studio.suggestions")}
                            </p>
                            <ul className="mt-1 flex flex-col gap-1.5">
                              {d.suggestions.map((s, i) => (
                                <li
                                  key={i}
                                  className="rounded-lg border border-zinc-100 px-3 py-2 text-xs text-zinc-600"
                                >
                                  <b>{s.issue}</b> → {s.fix}
                                  {s.example && (
                                    <span className="mt-1 block text-zinc-400">
                                      e.g. {s.example}
                                    </span>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {d.viewpoints &&
                          d.viewpoints.length > 0 &&
                          (() => {
                            const differing = d.viewpoints!.filter(
                              (v) => typeof v.band === "number" && v.band !== d.band
                            );
                            const seen = new Set<string>();
                            const list = differing.filter((v) => {
                              const k = v.rationale.slice(0, 24);
                              if (seen.has(k)) return false;
                              seen.add(k);
                              return true;
                            });
                            return (
                              <div className="mt-2">
                                <p className="text-xs font-medium text-zinc-400">
                                  {t("studio.viewpoints")}
                                  {list.length > 0 ? ` (${list.length})` : ""}
                                </p>
                                {list.length === 0 ? (
                                  <p className="mt-1 text-xs text-zinc-400">
                                    {t("studio.viewpoints_aligned")}
                                  </p>
                                ) : (
                                  <ul className="mt-1 flex flex-col gap-2">
                                    {list.map((v) => (
                                      <li
                                        key={v.expert}
                                        className="rounded-lg border border-zinc-100 px-3 py-2 text-xs text-zinc-600"
                                      >
                                        <b>{v.label}</b>
                                        {typeof v.band === "number" ? ` · ${v.band}/5` : ""}：
                                        {v.rationale}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            );
                          })()}
                      </details>
                    </div>
                  ))}
              </div>
            </section>
          )}

          {/* Rewrite */}
          {current && (
            <section className="rounded-3xl border border-zinc-200/80 bg-white p-6">
              {card?.experts && card.experts.length > 0 && (
                <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-zinc-400">{t("studio.adopt")}:</span>
                  {card.experts.map((e) => (
                    <button
                      key={e.key}
                      onClick={() =>
                        setAdopt((prev) =>
                          prev.includes(e.key)
                            ? prev.filter((k) => k !== e.key)
                            : [...prev, e.key]
                        )
                      }
                      className={`rounded-full px-3 py-1 font-medium transition ${
                        adopt.includes(e.key)
                          ? "bg-zinc-900 text-white"
                          : "border border-zinc-200 text-zinc-500 hover:bg-zinc-50"
                      }`}
                    >
                      {e.label}
                    </button>
                  ))}
                  <span className="text-zinc-300">{t("studio.adopt_hint")}</span>
                </div>
              )}
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
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-medium text-zinc-400">
                      {rewrite.kind === "full" ? t("studio.revised") : rewrite.kind === "title" ? t("studio.title_options") : t("studio.hook_options")}
                    </p>
                    {rewrite.kind === "full" && rewrite.meta?.diff && (
                      <button
                        onClick={() => setShowDiff((v) => !v)}
                        className="rounded-full border border-zinc-200 px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
                      >
                        {showDiff ? t("studio.final") : t("studio.compare")}
                      </button>
                    )}
                  </div>
                  {rewrite.kind === "full" && showDiff && rewrite.meta?.diff ? (
                    <div className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl border border-zinc-200 bg-white p-4 text-sm leading-relaxed">
                      {rewrite.meta.diff.map((seg, i) =>
                        seg.op === "insert" ? (
                          <span key={i} className="bg-emerald-50 text-emerald-700 underline decoration-emerald-400">
                            {seg.text}
                          </span>
                        ) : seg.op === "delete" ? (
                          <span key={i} className="text-red-400 line-through">
                            {seg.text}
                          </span>
                        ) : (
                          <span key={i} className="text-zinc-700">
                            {seg.text}
                          </span>
                        )
                      )}
                    </div>
                  ) : (
                    <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl border border-zinc-200 bg-zinc-50/70 p-4 text-sm leading-relaxed text-zinc-700">
                      {formatRewrite(rewrite)}
                    </pre>
                  )}

                  {rewrite.kind === "full" && rewrite.meta?.audit && (
                    <div
                      className={`mt-3 rounded-2xl border p-4 text-xs ${
                        rewrite.meta.audit.status === "APPROVED"
                          ? "border-emerald-200 bg-emerald-50/60"
                          : "border-amber-200 bg-amber-50/60"
                      }`}
                    >
                      <p className="font-medium text-zinc-700">
                        {t("studio.audit")} ·{" "}
                        <span
                          className={
                            rewrite.meta.audit.status === "APPROVED"
                              ? "text-emerald-700"
                              : "text-amber-700"
                          }
                        >
                          {rewrite.meta.audit.status || "-"}
                        </span>
                      </p>
                      <ul className="mt-2 grid gap-1 sm:grid-cols-2">
                        {Object.entries(rewrite.meta.audit.audit_results ?? {}).map(([k, v]) => (
                          <li key={k} className="flex items-center gap-2 text-zinc-600">
                            <span className={v === "PASS" ? "text-emerald-600" : "text-amber-600"}>
                              {v === "PASS" ? "✔" : "!"}
                            </span>
                            <span className="font-mono text-[11px]">{k}</span>
                          </li>
                        ))}
                      </ul>
                      {rewrite.meta.audit.audit_notes && (
                        <p className="mt-2 leading-relaxed text-zinc-600">
                          {rewrite.meta.audit.audit_notes}
                        </p>
                      )}
                    </div>
                  )}

                  {rewrite.kind === "full" &&
                    (rewrite.meta?.changelog?.length ?? 0) > 0 && (
                      <details className="mt-3 rounded-2xl border border-zinc-200 p-4">
                        <summary className="cursor-pointer text-xs font-medium text-zinc-400 transition hover:text-zinc-600">
                          {t("studio.changelog")}
                        </summary>
                        <ul className="mt-2 flex flex-col gap-2">
                          {rewrite.meta!.changelog!.map((c, i) => (
                            <li key={i} className="rounded-xl border border-zinc-100 px-3 py-2 text-xs">
                              <p className="text-zinc-700">
                                {c.change}
                                {c.verified === false && (
                                  <span className="ml-2 text-amber-600">· {t("studio.unverified")}</span>
                                )}
                              </p>
                              {c.why && <p className="mt-0.5 text-zinc-400">{c.why}</p>}
                              {(c.original || c.revised) && (
                                <p className="mt-1 text-zinc-500">
                                  {c.original && <span className="line-through">{c.original}</span>}
                                  {c.original && c.revised && <span className="mx-1">→</span>}
                                  {c.revised && <span className="text-zinc-700">{c.revised}</span>}
                                </p>
                              )}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                </div>
              )}
            </section>
          )}

          {/* History */}
          <section className="rounded-3xl border border-zinc-200/80 bg-white p-6">
            <h2 className="text-lg font-semibold">{t("studio.history")}</h2>
            {docs.length === 0 && (
              <div className="mt-3 rounded-2xl border border-dashed border-zinc-200 bg-zinc-50/60 px-5 py-8 text-center">
                <p className="text-sm font-medium text-zinc-600">{t("studio.no_docs")}</p>
                <p className="mx-auto mt-1.5 max-w-sm text-xs leading-relaxed text-zinc-400">
                  {t("studio.no_docs_hint")}
                </p>
              </div>
            )}
            <div className="mt-3 flex flex-col gap-2">
              {docs.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center gap-2 rounded-xl border border-zinc-200/80 px-2 py-1.5 transition hover:bg-zinc-50"
                >
                  <button
                    onClick={() => openDoc(d.id)}
                    className="flex flex-1 items-center justify-between gap-3 px-2 py-1 text-left"
                  >
                    <span className="truncate text-sm text-zinc-700">{d.title || "Untitled"}</span>
                    <span className="shrink-0 text-xs text-zinc-400">
                      {d.platform} · {d.char_count} {t("studio.chars")}
                    </span>
                  </button>
                  <button
                    onClick={() => void deleteDoc(d.id)}
                    className="shrink-0 rounded-full px-3 py-1 text-xs text-zinc-400 transition hover:bg-red-50 hover:text-red-600"
                    title={t("common.delete")}
                  >
                    {t("common.delete")}
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {quotaOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 p-4 backdrop-blur-sm"
          onClick={() => setQuotaOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-3xl bg-white p-6 text-center shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-2xl">
              ☕
            </div>
            <h2 className="mt-4 text-base font-semibold text-zinc-900">
              {t("studio.quota_title")}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-zinc-500">
              {t("studio.quota_body", { limit: String(quota?.limit ?? 3) })}
            </p>
            <div className="mt-5 flex flex-col gap-2">
              <button
                onClick={() => setQuotaOpen(false)}
                className="w-full rounded-full bg-zinc-900 px-5 py-2.5 text-sm text-white"
              >
                {t("studio.quota_got_it")}
              </button>
              <button
                onClick={() => {
                  setQuotaOpen(false);
                  refreshDocs();
                }}
                className="w-full rounded-full px-5 py-2.5 text-sm text-zinc-500 hover:bg-zinc-50"
              >
                {t("studio.quota_view_history")}
              </button>
            </div>
          </div>
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
