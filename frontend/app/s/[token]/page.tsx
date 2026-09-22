import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import RadarChart from "../../../components/RadarChart";

export const dynamic = "force-dynamic";

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000/api";

type Dimension = {
  key: string;
  label: string;
  band: number;
  score: number;
  weight: number;
  rationale: string;
  suggestions: { issue: string; fix: string; example?: string }[];
  evidence: { quote: string; location?: string }[];
};
type Shared = {
  platform: string;
  archetype: string;
  lang: "zh" | "en";
  title: string;
  overall_score: number;
  summary: string;
  consensus: {
    strengths?: string[];
    weaknesses?: string[];
    must_fix?: string[];
    top_priorities?: { point: string; impact?: string }[];
    disagreement?: { key: string; note: string }[];
  };
  dimensions: Dimension[];
  experts: { key: string; label: string; overall: number }[];
  created_at: string | null;
  include_content: boolean;
  content?: string;
  views: number;
};

async function loadShare(token: string): Promise<Shared | null> {
  try {
    const res = await fetch(`${API}/share/${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Shared;
  } catch {
    return null;
  }
}

const L = {
  zh: {
    score: "总分",
    band: "档位",
    weight: "权重",
    summary: "委员会总评",
    strengths: "共识优势",
    weaknesses: "共识劣势",
    must_fix: "必改项",
    priorities: "优先修改",
    dimensions: "各维度评分",
    content: "原文",
    cta: "给你的文案也打一次分",
    ctaSub: "五位专家 · 六个维度 + 事实严谨度 · 免费",
    open: "免费开始",
    views: "次浏览",
    shared: "分享的评分卡",
  },
  en: {
    score: "Overall",
    band: "Band",
    weight: "Weight",
    summary: "Committee summary",
    strengths: "Consensus strengths",
    weaknesses: "Consensus weaknesses",
    must_fix: "Must fix",
    priorities: "Top priorities",
    dimensions: "Dimension scores",
    content: "Original copy",
    cta: "Score your own copy",
    ctaSub: "Five experts · six dimensions plus factual rigor · free",
    open: "Start free",
    views: "views",
    shared: "Shared scorecard",
  },
} as const;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const data = await loadShare(token);
  if (!data) return { title: "Scorecard not found" };
  const title = `${data.title} — ${data.overall_score}/100 · NotesBang`;
  const description =
    data.summary ||
    "A platform-aware scorecard from the NotesBang review committee.";
  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function SharedScorecardPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const data = await loadShare(token);
  if (!data) notFound();
  const t = L[data.lang] ?? L.en;
  const created = data.created_at ? new Date(data.created_at) : null;

  return (
    <main id="main" className="min-h-[100dvh] bg-zinc-50/60 font-sans text-zinc-900 antialiased">
      <header className="border-b border-black/5 bg-white">
        <div className="mx-auto flex h-14 w-full max-w-4xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 text-sm font-bold text-white">
              NB
            </span>
            NotesBang
          </Link>
          <Link
            href="/studio"
            className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-zinc-700 active:scale-[0.98]"
          >
            {t.open}
          </Link>
        </div>
      </header>

      <article className="mx-auto w-full max-w-4xl px-6 py-10">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">
          {t.shared}
        </p>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="max-w-2xl text-2xl font-semibold tracking-tight sm:text-3xl">
              {data.title}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span className="rounded-full border border-zinc-200 bg-white px-3 py-1">
                {data.platform}
              </span>
              <span className="rounded-full border border-zinc-200 bg-white px-3 py-1">
                {data.archetype}
              </span>
              {created && <span>{created.toLocaleDateString()}</span>}
              <span className="tnum">
                {data.views} {t.views}
              </span>
            </div>
          </div>
          <div className="rounded-3xl bg-zinc-900 px-6 py-4 text-center text-white">
            <p className="text-xs text-zinc-400">{t.score}</p>
            <p className="tnum text-4xl font-semibold">{data.overall_score}</p>
            <p className="text-xs text-zinc-500">/100</p>
          </div>
        </div>

        <section className="mt-8 grid gap-6 rounded-3xl border border-zinc-200/80 bg-white p-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <RadarChart
            axes={data.dimensions.map((d) => d.label)}
            series={[
              {
                label: t.score,
                color: "#18181b",
                values: data.dimensions.map((d) => d.score),
              },
            ]}
          />
          <div className="flex flex-col gap-4">
            {data.summary && (
              <div>
                <p className="text-xs font-medium text-zinc-400">{t.summary}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-zinc-600">{data.summary}</p>
              </div>
            )}
            {(data.consensus.must_fix?.length ?? 0) > 0 && (
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
                <p className="text-xs font-medium text-red-700">{t.must_fix}</p>
                <ul className="mt-2 flex flex-col gap-1 text-sm leading-relaxed text-red-800">
                  {data.consensus.must_fix!.map((m, i) => (
                    <li key={i}>· {m}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              {(data.consensus.strengths?.length ?? 0) > 0 && (
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4">
                  <p className="text-xs font-medium text-emerald-700">{t.strengths}</p>
                  <ul className="mt-2 flex flex-col gap-1 text-sm leading-relaxed text-emerald-900">
                    {data.consensus.strengths!.map((s, i) => (
                      <li key={i}>· {s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(data.consensus.weaknesses?.length ?? 0) > 0 && (
                <div className="rounded-2xl border border-rose-100 bg-rose-50/50 p-4">
                  <p className="text-xs font-medium text-rose-700">{t.weaknesses}</p>
                  <ul className="mt-2 flex flex-col gap-1 text-sm leading-relaxed text-rose-900">
                    {data.consensus.weaknesses!.map((w, i) => (
                      <li key={i}>· {w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="mt-6">
          <h2 className="text-sm font-medium text-zinc-500">{t.dimensions}</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {[...data.dimensions]
              .sort((a, b) => a.score - b.score)
              .map((d) => (
                <div key={d.key} className="rounded-2xl border border-zinc-200/80 bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{d.label}</span>
                    <span className="tnum shrink-0 rounded-full bg-zinc-100 px-2.5 py-1 text-xs text-zinc-600">
                      {d.score}/100 · {t.band} {d.band}/5 · {Math.round(d.weight * 100)}%
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
                  {d.evidence.length > 0 && (
                    <blockquote className="mt-3 rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
                      “{d.evidence[0].quote}”
                    </blockquote>
                  )}
                  {d.suggestions.length > 0 && (
                    <ul className="mt-3 flex flex-col gap-1.5">
                      {d.suggestions.map((s, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-zinc-100 px-3 py-2 text-xs text-zinc-600"
                        >
                          <b>{s.issue}</b> → {s.fix}
                          {s.example && (
                            <span className="mt-1 block text-zinc-400">e.g. {s.example}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
          </div>
        </section>

        {data.include_content && data.content && (
          <section className="mt-6 rounded-2xl border border-zinc-200/80 bg-white p-5">
            <h2 className="text-sm font-medium text-zinc-500">{t.content}</h2>
            <pre className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-zinc-700">
              {data.content}
            </pre>
          </section>
        )}

        <section className="mt-8 rounded-3xl bg-zinc-950 px-6 py-10 text-center text-white">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">{t.cta}</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-400">{t.ctaSub}</p>
          <Link
            href="/studio"
            className="mt-6 inline-flex items-center justify-center rounded-full bg-white px-7 py-3 text-[15px] font-medium text-zinc-900 transition hover:bg-zinc-200 active:scale-[0.98]"
          >
            {t.open}
          </Link>
        </section>
      </article>
    </main>
  );
}
