"use client";

import Link from "next/link";
import {
  DownloadSimple,
  Gift,
  ListChecks,
  MagicWand,
  Quotes,
  SquaresFour,
} from "@phosphor-icons/react/dist/ssr";
import LanguageSwitcher from "../components/LanguageSwitcher";
import RadarChart from "../components/RadarChart";
import Reveal from "../components/Reveal";
import { FREE_DAILY_LIMIT } from "../lib/config";
import { useI18n } from "../lib/i18n";

type Copy = {
  nav: { features: string; how: string; faq: string; open: string };
  hero: { badge: string; title1: string; title2: string; sub: string; cta: string; more: string };
  mock: { title: string; platform: string; overall: string; dim: string; band: string; quote: string; suggestion: string; evidence: string; dims: { t: string; v: number }[] };
  platforms: string[];
  features: { title: string; items: { t: string; b: string }[] };
  how: { title: string; steps: { t: string; b: string }[]; cta: string };
  free: { title: string; sub: string; bullets: string[] };
  faq: { title: string; items: { q: string; a: string }[] };
  cta: { title: string; sub: string; button: string };
  footer: { tagline: string };
};

const FEATURE_ICONS = [
  SquaresFour,
  Quotes,
  ListChecks,
  MagicWand,
  DownloadSimple,
  Gift,
];

const COPY: Record<"en" | "zh", Copy> = {
  en: {
    nav: { features: "Features", how: "How it works", faq: "FAQ", open: "Start free" },
    hero: {
      badge: "Content scoring & rewriting, made for your platform",
      title1: "Paste your copy.",
      title2: "See exactly why it works, or why it doesn't.",
      sub: "Score your article or note across hook, rhythm, emotion, social currency and more, with evidence from your own text. Then rewrite it: full version plus title and opening options.",
      cta: "Start free →",
      more: "See how it works",
    },
    mock: {
      title: "Scorecard",
      platform: "Xiaohongshu",
      overall: "Overall",
      dim: "Hook strength",
      band: "Band 3/5",
      quote: "I grew from 0 to 10k followers in 3 months…",
      suggestion: "Lead with the outcome before the backstory.",
      evidence: "Evidence from your copy",
      dims: [
        { t: "Hook", v: 64 },
        { t: "Title", v: 72 },
        { t: "Rhythm", v: 58 },
        { t: "Emotion", v: 81 },
        { t: "Social", v: 66 },
        { t: "Reply", v: 54 },
      ],
    },
    platforms: ["Xiaohongshu", "WeChat", "LinkedIn", "X", "Blog"],
    features: {
      title: "Scoring you can trust, rewriting you can ship.",
      items: [
        { t: "Platform rubrics", b: "Xiaohongshu, WeChat, LinkedIn, X and Blog each get their own weights and norms." },
        { t: "Evidence-based scores", b: "Every score cites exact lines from your copy, so you see the reason, not just a number." },
        { t: "Actionable suggestions", b: "Issue → fix → a ready-to-paste example for each dimension." },
        { t: "Full rewrite + variants", b: "Get a rewritten piece plus 5 titles and 3 opening hooks." },
        { t: "Export anywhere", b: "Download the scorecard and rewrite as Markdown, Word or plain text." },
        { t: "Free to start", b: `${FREE_DAILY_LIMIT} analyses per day, up to 3000 characters each. No card needed.` },
      ],
    },
    how: {
      title: "From draft to ready, in three steps.",
      steps: [
        { t: "Paste or upload", b: "Paste text or upload .docx / .txt / .md and pick the platform you publish on." },
        { t: "Get your scorecard", b: "See band-by-band scores with evidence and concrete fixes." },
        { t: "Rewrite & export", b: "Apply a full rewrite with title and hook options, then export." },
      ],
      cta: "Start free",
    },
    free: {
      title: "Free during early access.",
      sub: "Help us learn what makes copy work, and get your analysis free.",
      bullets: [
        `${FREE_DAILY_LIMIT} analyses per day, up to 3000 characters each`,
        "No credit card required",
        "Your copy is used (anonymized) to improve the service. You can opt out anytime",
      ],
    },
    faq: {
      title: "Frequently asked questions",
      items: [
        { q: "Which formats can I upload?", a: "Paste plain text, or upload .docx, .txt or .md. Each piece is capped at 3000 characters to keep scoring fast and free." },
        { q: "How is the score computed?", a: "Each dimension is rated on a 1–5 band using a platform-specific rubric, and the overall score is the weighted average computed by our system, not guessed by the model." },
        { q: "Is there an 'AI probability' score?", a: "No. AI-text detection is unreliable, so we removed it. Instead we score things you can act on: hook, title, rhythm, emotion, social currency and interaction." },
        { q: "Will you use my copy?", a: "By default your anonymized copy helps us learn what works; you can turn this off per document or any time. See the Privacy Policy." },
        { q: "Does it work in Chinese and English?", a: "Yes. The UI and the scoring support both, and the output follows your copy's language." },
        { q: "Is it really free?", a: `Yes, during early access: ${FREE_DAILY_LIMIT} analyses per day per account, no card required.` },
      ],
    },
    cta: { title: "Your next piece deserves a second pair of eyes.", sub: "Score it free, see the reasons, ship a better version.", button: "Start free" },
    footer: { tagline: "NotesBang · content scoring & rewriting" },
  },
  zh: {
    nav: { features: "功能", how: "流程", faq: "常见问题", open: "免费开始" },
    hero: {
      badge: "为你的发布平台而做的文案评分与改写",
      title1: "粘贴你的文案。",
      title2: "看清它为什么行 —— 或不行。",
      sub: "从首屏钩子、推进节奏、情绪共鸣、社交货币等多个维度打分，并引用你自己的原文作为证据；再给出整篇改写，以及标题与开头的多个备选。",
      cta: "免费开始 →",
      more: "看看怎么用",
    },
    mock: {
      title: "评分卡",
      platform: "小红书",
      overall: "总分",
      dim: "首屏钩子穿透力",
      band: "档位 3/5",
      quote: "我用3个月把粉丝从0做到1万……",
      suggestion: "先给结论，再讲背景。",
      evidence: "来自你原文的证据",
      dims: [
        { t: "钩子", v: 64 },
        { t: "标题", v: 72 },
        { t: "节奏", v: 58 },
        { t: "情绪", v: 81 },
        { t: "社交", v: 66 },
        { t: "互动", v: 54 },
      ],
    },
    platforms: ["小红书", "公众号", "LinkedIn", "X", "博客"],
    features: {
      title: "可信的评分，能用的改写。",
      items: [
        { t: "平台化 Rubric", b: "小红书、公众号、LinkedIn、X、博客各有独立的权重与规范。" },
        { t: "有证据的评分", b: "每一分都引用你的原文原句，看到的是理由，而不只是数字。" },
        { t: "可执行的建议", b: "每个维度给出：问题 → 怎么改 → 可直接粘贴的示例。" },
        { t: "整篇改写 + 多版本", b: "一篇改写稿，外加 5 个标题与 3 个开头备选。" },
        { t: "随手导出", b: "评分卡与改写稿可导出 Markdown、Word 或纯文本。" },
        { t: "免费开始", b: `每天 ${FREE_DAILY_LIMIT} 次分析，单篇不超过 3000 字，无需绑卡。` },
      ],
    },
    how: {
      title: "三步，从草稿到可用。",
      steps: [
        { t: "粘贴或上传", b: "粘贴文本，或上传 .docx / .txt / .md，并选择你要发布的平台。" },
        { t: "拿到评分卡", b: "逐维度查看档位、原文证据与具体修改建议。" },
        { t: "改写与导出", b: "应用整篇改写（含标题/开头备选），然后导出。" },
      ],
      cta: "免费开始",
    },
    free: {
      title: "早期体验期，完全免费。",
      sub: "帮我们一起摸清“什么样的文案有效”，你的分析免费。",
      bullets: [
        `每天 ${FREE_DAILY_LIMIT} 次分析，单篇不超过 3000 字`,
        "无需绑定信用卡",
        "你的文案会以匿名方式用于改进服务，可随时关闭",
      ],
    },
    faq: {
      title: "常见问题",
      items: [
        { q: "支持哪些格式？", a: "可直接粘贴文本，或上传 .docx、.txt、.md。单篇上限 3000 字，以保证快速与免费。" },
        { q: "分数是怎么算的？", a: "每个维度按 1–5 档评分（平台专属 Rubric），总分由系统按权重计算得出，而不是让模型随意给分。" },
        { q: "为什么没有“AI 撰写概率”？", a: "AI 文本检测并不可靠，所以去掉了。我们只评你可以改进的维度：钩子、标题、节奏、情绪、社交货币与互动。" },
        { q: "会用我的文案吗？", a: "默认会以匿名方式用于改进服务，你可以对单篇或随时关闭。详见隐私政策。" },
        { q: "中英文都支持吗？", a: "支持——界面与评分都兼容中英文，输出语言跟随你的文案。" },
        { q: "真的免费吗？", a: `早期体验期免费：每账号每天 ${FREE_DAILY_LIMIT} 次分析，无需绑卡。` },
      ],
    },
    cta: { title: "你的下一篇文案，值得再被看一遍。", sub: "免费评分，看清理由，交付更好的版本。", button: "免费开始" },
    footer: { tagline: "NotesBang · 文案评分与改写" },
  },
};

export default function Landing() {
  const { locale } = useI18n();
  const c = COPY[locale] ?? COPY.en;

  return (
    <main id="main" className="min-h-full bg-white font-sans text-zinc-900 antialiased">
      <header className="sticky top-0 z-20 border-b border-black/5 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-6">
          <a href="#top" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 text-sm font-bold text-white">NB</span>
            NotesBang
          </a>
          <nav className="hidden items-center gap-6 text-sm text-zinc-500 md:flex">
            <a href="#features" className="transition hover:text-zinc-900">{c.nav.features}</a>
            <a href="#how" className="transition hover:text-zinc-900">{c.nav.how}</a>
            <a href="#faq" className="transition hover:text-zinc-900">{c.nav.faq}</a>
          </nav>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link href="/studio" className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-zinc-700 active:scale-[0.98]">
              {c.nav.open}
            </Link>
          </div>
        </div>
      </header>

      <section id="top" className="relative overflow-hidden bg-gradient-to-b from-zinc-50 to-white">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgba(9,9,11,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(9,9,11,0.05) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
            maskImage:
              "radial-gradient(ellipse 75% 55% at 50% 0%, #000 25%, transparent 75%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 75% 55% at 50% 0%, #000 25%, transparent 75%)",
          }}
        />
        <div className="relative mx-auto flex max-w-4xl flex-col items-center px-6 pt-20 text-center sm:pt-24">
          <Reveal className="flex flex-col items-center">
            <span className="rounded-full border border-zinc-200 bg-white px-4 py-1.5 text-[13px] font-medium tracking-wide text-zinc-500">
              {c.hero.badge}
            </span>
            <h1 className="mt-6 max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-balance sm:text-6xl sm:leading-[1.05]">
              {c.hero.title1}
              <br />
              {c.hero.title2}
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-zinc-500">{c.hero.sub}</p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/studio" className="rounded-full bg-zinc-900 px-7 py-3 text-[15px] font-medium text-white shadow-sm transition hover:bg-zinc-700 active:scale-[0.98]">
                {c.hero.cta}
              </Link>
              <a href="#how" className="rounded-full border border-zinc-300 bg-white px-7 py-3 text-[15px] font-medium text-zinc-700 transition hover:bg-zinc-50 active:scale-[0.98]">
                {c.hero.more}
              </a>
            </div>
            <ul className="mt-8 flex flex-wrap items-center justify-center gap-2">
              {c.platforms.map((p) => (
                <li
                  key={p}
                  className="rounded-full border border-zinc-200 bg-white/70 px-3 py-1 text-xs text-zinc-500"
                >
                  {p}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>

        <div className="relative mx-auto mt-14 w-full max-w-5xl px-6 pb-24">
          <Reveal delay={0.08}>
            <div className="relative mx-auto max-w-3xl overflow-hidden rounded-[28px] border border-zinc-200/80 bg-white shadow-[0_40px_80px_-40px_rgba(24,24,27,0.35)]">
              <div className="flex items-center gap-2 border-b border-zinc-100 bg-zinc-50/80 px-5 py-3">
                <span className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
                <span className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
                <span className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
                <span className="ml-3 text-xs text-zinc-400">NotesBang Studio</span>
              </div>
              <div className="p-6 sm:p-8">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm font-medium text-zinc-900">{c.mock.title}</p>
                  <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs text-zinc-500">
                    {c.mock.platform}
                  </span>
                </div>

                <div className="mt-6 grid items-center gap-6 sm:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
                  <RadarChart
                    axes={c.mock.dims.map((d) => d.t)}
                    series={[
                      {
                        label: c.mock.overall,
                        color: "#18181b",
                        values: c.mock.dims.map((d) => d.v),
                      },
                    ]}
                  />
                  <div className="flex flex-col gap-4">
                    <div className="flex items-end justify-between rounded-2xl bg-zinc-900 px-5 py-4 text-white">
                      <span className="text-xs text-zinc-400">{c.mock.overall}</span>
                      <span className="tnum text-3xl font-semibold">78/100</span>
                    </div>
                    <ul className="flex flex-col gap-3">
                      {c.mock.dims.map((d) => (
                        <li key={d.t}>
                          <div className="flex items-center justify-between text-xs text-zinc-500">
                            <span>{d.t}</span>
                            <span className="tnum text-zinc-400">{d.v}</span>
                          </div>
                          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
                            <div
                              className="h-full rounded-full bg-zinc-800"
                              style={{ width: `${d.v}%` }}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="mt-6 rounded-2xl border border-zinc-100 bg-zinc-50/70 px-5 py-4">
                  <p className="text-xs font-medium text-zinc-400">{c.mock.evidence}</p>
                  <p className="mt-1.5 text-sm text-zinc-600">“{c.mock.quote}”</p>
                  <p className="mt-2 text-sm text-zinc-900">→ {c.mock.suggestion}</p>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section id="features" className="border-t border-black/5 bg-white py-24">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="mx-auto max-w-2xl text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{c.features.title}</h2>
          <div className="mt-14 grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {c.features.items.map((f, i) => {
              const Icon = FEATURE_ICONS[i % FEATURE_ICONS.length];
              return (
                <Reveal key={f.t} delay={i * 0.06}>
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-200/80 bg-zinc-50 text-zinc-900">
                    <Icon size={22} weight="duotone" />
                  </span>
                  <h3 className="mt-4 text-lg font-semibold tracking-tight">{f.t}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-zinc-500">{f.b}</p>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      <section id="how" className="border-t border-black/5 bg-zinc-50 py-24">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="mx-auto max-w-2xl text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{c.how.title}</h2>
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {c.how.steps.map((s, i) => (
              <Reveal
                key={s.t}
                delay={i * 0.08}
                className="rounded-3xl border border-black/5 bg-white p-7 transition duration-300 hover:-translate-y-1 hover:shadow-xl"
              >
                <p className="font-mono text-2xl font-semibold text-zinc-200">{String(i + 1).padStart(2, "0")}</p>
                <h3 className="mt-4 text-xl font-semibold tracking-tight">{s.t}</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-zinc-500">{s.b}</p>
              </Reveal>
            ))}
          </div>
          <div className="mt-12 text-center">
            <Link href="/studio" className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-7 py-3 text-[15px] font-medium text-white transition hover:bg-zinc-700 active:scale-[0.98]">
              {c.how.cta}
            </Link>
          </div>
        </div>
      </section>

      <section id="free" className="border-t border-black/5 bg-white py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{c.free.title}</h2>
          <p className="mt-3 text-zinc-500">{c.free.sub}</p>
          <ul className="mx-auto mt-8 flex max-w-md flex-col gap-2 text-left text-[15px] text-zinc-600">
            {c.free.bullets.map((b) => (
              <li key={b} className="flex items-center gap-2">
                <span className="text-emerald-500">✓</span>
                {b}
              </li>
            ))}
          </ul>
          <Link href="/studio" className="mt-8 inline-flex items-center justify-center rounded-full bg-zinc-900 px-7 py-3 text-[15px] font-medium text-white transition hover:bg-zinc-700 active:scale-[0.98]">
            {c.nav.open}
          </Link>
        </div>
      </section>

      <section id="faq" className="border-t border-black/5 bg-white py-24">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{c.faq.title}</h2>
          <div className="mt-10 divide-y divide-zinc-100 border-y border-zinc-100">
            {c.faq.items.map((item) => (
              <details key={item.q} className="group py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-medium text-zinc-900 [&::-webkit-details-marker]:hidden">
                  {item.q}
                  <span className="text-zinc-300 transition-transform group-open:rotate-45">＋</span>
                </summary>
                <p className="mt-3 text-[15px] leading-relaxed text-zinc-500">{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-zinc-950 py-20 text-center text-white">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.06) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
            maskImage:
              "radial-gradient(ellipse 70% 60% at 50% 40%, #000 20%, transparent 75%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 70% 60% at 50% 40%, #000 20%, transparent 75%)",
          }}
        />
        <div className="relative">
          <h2 className="mx-auto max-w-2xl px-6 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{c.cta.title}</h2>
          <p className="mx-auto mt-4 max-w-xl px-6 text-zinc-400">{c.cta.sub}</p>
          <Link href="/studio" className="mt-8 inline-flex items-center justify-center rounded-full bg-white px-7 py-3 text-[15px] font-medium text-zinc-900 transition hover:bg-zinc-200 active:scale-[0.98]">
            {c.cta.button}
          </Link>
        </div>
      </section>

      <footer className="bg-zinc-950 pb-10 pt-2 text-sm text-zinc-500">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 sm:flex-row">
          <p>{c.footer.tagline}</p>
          <nav className="flex items-center gap-4 text-xs text-zinc-600">
            <a href="/studio" className="transition hover:text-zinc-300">Studio</a>
            <a href="/terms" className="transition hover:text-zinc-300">Terms</a>
            <a href="/privacy" className="transition hover:text-zinc-300">Privacy</a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
