import Link from "next/link";
import FeatureCarousel from "../components/FeatureCarousel";

const features = [
  {
    title: "Made for the moment",
    body: "Boardroom, classroom, keynote or a pitch on a deadline — the notes are shaped for the scenario you're actually in, never a one-size-fits-all script.",
    mark: "B",
  },
  {
    title: "Notes that fit your time",
    body: "We measure your speaking pace first, then allocate a word budget per slide from your target duration. Your notes finish right on time.",
    mark: "T",
  },
  {
    title: "Your voice, preserved",
    body: "Choose a style, describe your context — or upload past scripts and let the generator learn the way you talk.",
    mark: "V",
  },
  {
    title: "Full script ⇄ cue cards",
    body: "Get a complete read-aloud script by default, or switch to bullet-style cue cards. Two formats, whichever fits how you present.",
    mark: "C",
  },
  {
    title: "Coherent across the deck",
    body: "An outline pass runs first, then notes are generated section by section — pages reference each other naturally. Mark key slides to go deeper.",
    mark: "L",
  },
  {
    title: "Back into PowerPoint",
    body: "Write notes into each slide's speaker notes, or export a Word/PDF script. Your original layout is never touched.",
    mark: "P",
  },
];

const steps = [
  {
    n: "01",
    title: "Upload your deck",
    body: "Bring your slides (PPTX and slide-style PDF). We extract every page and let you confirm sections and flag key slides before anything is written.",
  },
  {
    n: "02",
    title: "Set the scene and duration",
    body: "Pick a style that matches your moment, describe the audience, and set your time limit. Read a short sample aloud to calibrate your pace — or skip it.",
  },
  {
    n: "03",
    title: "Generate, polish, export",
    body: "Notes are written page by page as one coherent flow. Regenerate a single slide, edit freely, then export back to PPTX or as a script.",
  },
];

const pricing = [
  { points: 2, usd: 0, per: 0, note: "Preview one small deck, free", free: true },
  { points: 10, usd: 5, per: 0.5, note: "Try a couple of short decks" },
  { points: 20, usd: 10, per: 0.5, note: "Great for a few talks" },
  { points: 200, usd: 95, per: 0.475, note: "Most popular", featured: true },
  { points: 500, usd: 230, per: 0.46, note: "For frequent presenters" },
];

const faqs = [
  {
    q: "How does per-slide pricing work?",
    a: "One point = one generated slide ($0.50 at the base rate). Buy points in packs ($5 for 10, $10 for 20, $95 for 200, $230 for 500). Every account can preview one deck of up to two slides free, and only the slides you actually generate consume points — exports and edits never cost extra.",
  },
  {
    q: "Which file formats are supported?",
    a: "The MVP supports .pptx and slide-style PDFs (16:9 / 4:3 pages). Legacy .ppt, Word documents and text-style PDFs are not supported yet and are under evaluation.",
  },
  {
    q: "How much does it cost? Can I try it for free?",
    a: "After registering and verifying your email, each account gets a one-time trial: upload a deck of up to two slides and experience the full generation flow. Trial results can be previewed freely but cannot be exported until you top up, which also unlocks larger files.",
  },
  {
    q: "Do you generate full scripts or bullet points?",
    a: "Both. By default we produce a complete, read-aloud script; one click switches a page (or the whole deck) to concise cue-card style. Both honor your target duration.",
  },
  {
    q: "How do you make sure I finish on time?",
    a: "Read a short fixed sample so we can measure your real pace (or enter one manually / use the default). We compute a total word budget from pace × duration, allocate it per slide, and verify lengths after generation.",
  },
  {
    q: "Which languages are supported?",
    a: "Output language follows the document by default and can be overridden to Chinese, English, or another target language in the settings.",
  },
  {
    q: "What happens to my content?",
    a: "To write notes, your document content is sent to a third-party model (e.g. DeepSeek). Source files are only used for parsing and display, and you can delete projects at any time. See our privacy and data-handling policy inside the product.",
  },
  {
    q: "How do I make it sound more like me?",
    a: "In “My styles”, upload a few of your past scripts. We automatically extract your tone, sentence rhythm and structure, and reuse it on later generations. Samples belong to you and can be deleted anytime.",
  },
  {
    q: "Can I use it on my phone?",
    a: "Upload and editing work best in a desktop browser. Voice pacing requires browser recording support (Safari 16.4+); on mobile it gracefully falls back to manual pace entry.",
  },
];

export default function Landing() {
  return (
    <main className="min-h-full bg-white font-sans text-zinc-900 antialiased">
      {/* Nav */}
      <header className="sticky top-0 z-20 border-b border-black/5 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-6">
          <a href="#top" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 text-sm font-bold text-white">
              NB
            </span>
            NotesBang
          </a>
          <nav className="hidden items-center gap-6 text-sm text-zinc-500 md:flex">
            <a href="#features" className="transition hover:text-zinc-900">Features</a>
            <a href="#how" className="transition hover:text-zinc-900">How it works</a>
            <a href="#pricing" className="transition hover:text-zinc-900">Pricing</a>
            <a href="#faq" className="transition hover:text-zinc-900">FAQ</a>
          </nav>
          <Link
            href="/app"
            className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-zinc-700"
          >
            Open the app
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section id="top" className="relative overflow-hidden bg-gradient-to-b from-zinc-50 to-white">
        <div className="mx-auto flex max-w-4xl flex-col items-center px-6 pt-24 text-center sm:pt-32">
          <span className="rounded-full border border-zinc-200 bg-white px-4 py-1.5 text-[13px] font-medium tracking-wide text-zinc-500">
            Tailor-made notes for your very moment
          </span>
          <h1 className="mt-6 max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-balance sm:text-6xl sm:leading-[1.05]">
            Upload your slides.
            <br />
            Get a script built for this talk.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-zinc-500">
            Turning every page of your presentation into speaker notes matched to
            your pace, your time limit and your style — tuned to the moment and the
            audience you are speaking to, not a recycled template.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/app"
              className="rounded-full bg-zinc-900 px-7 py-3 text-[15px] font-medium text-white shadow-sm transition hover:bg-zinc-700"
            >
              Start your free trial →
            </Link>
            <a
              href="#features"
              className="rounded-full border border-zinc-300 bg-white px-7 py-3 text-[15px] font-medium text-zinc-700 transition hover:bg-zinc-50"
            >
              See what it does
            </a>
          </div>
        </div>

        {/* Product mock — bigger, clearer */}
        <div className="mx-auto mt-16 w-full max-w-5xl px-6 pb-24">
          <div className="relative mx-auto overflow-hidden rounded-[28px] border border-zinc-200/80 bg-white shadow-[0_40px_80px_-40px_rgba(0,0,0,0.3)]">
            <div className="flex flex-col gap-1 border-b border-zinc-100 px-7 py-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-[15px] font-medium">Notes preview</p>
                <div className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-xs text-zinc-500">
                  <span><b className="font-medium text-zinc-400">Style:</b> Business</span>
                  <span><b className="font-medium text-zinc-400">Notes mode:</b> Full script</span>
                  <span><b className="font-medium text-zinc-400">Time limit:</b> 10 min</span>
                  <span><b className="font-medium text-zinc-400">Pace:</b> yours</span>
                </div>
              </div>
              <span className="mt-2 shrink-0 self-start rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-600 sm:mt-0 sm:self-auto">
                Estimated ~9.7 min
              </span>
            </div>

            <div className="grid gap-5 px-7 py-6 sm:grid-cols-2">
              <div className="rounded-2xl bg-zinc-50 p-5">
                <p className="text-xs font-medium text-zinc-400">Slide 1 · Opening</p>
                <p className="mt-3 text-[15px] leading-relaxed text-zinc-700">
                  Hi everyone — in the next ten minutes I'll show you how we turn a deck into a talk
                  you can actually give. Let's start with a problem you've all felt.
                </p>
              </div>
              <div className="rounded-2xl bg-zinc-900 p-5">
                <p className="text-xs font-medium text-zinc-500">Slide 3 · Data (key slide)</p>
                <p className="mt-3 text-[15px] leading-relaxed text-zinc-200">
                  72% of presenters start the night before. That number is from our internal survey —
                  <span className="font-medium text-white"> [slow down] </span>
                  and it tells us this tool isn't a luxury.
                </p>
              </div>
            </div>

            {/* Capabilities — the “what you can do” band */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-2 border-t border-zinc-100 bg-zinc-50/70 px-7 py-4">
              <span className="mr-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
                What you can do with the result
              </span>
              {["Regenerate a slide", "Switch to cue cards", "Write back to PPTX", "Export Word", "Export PDF"].map(
                (cap) => (
                  <span
                    key={cap}
                    className="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-600"
                  >
                    {cap}
                  </span>
                )
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Features — horizontal, swipeable */}
      <section id="features" className="border-t border-black/5 bg-white py-24">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-center text-sm font-medium uppercase tracking-widest text-zinc-400">
            Features
          </p>
          <h2 className="mx-auto mt-3 max-w-2xl text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Preparing a talk, made fast and personal.
          </h2>
        </div>
        <FeatureCarousel items={features} />
      </section>

      {/* How it works — steps zoom on hover */}
      <section id="how" className="border-t border-black/5 bg-zinc-50 py-24">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-center text-sm font-medium uppercase tracking-widest text-zinc-400">
            Three steps
          </p>
          <h2 className="mx-auto mt-3 max-w-2xl text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            From upload to on stage, in three steps.
          </h2>
          <div className="mt-16 grid gap-6 md:grid-cols-3">
            {steps.map((s) => (
              <div
                key={s.n}
                className="group cursor-default rounded-3xl border border-black/5 bg-white p-8 transition duration-300 ease-out hover:-translate-y-2 hover:scale-[1.03] hover:border-zinc-300 hover:shadow-[0_30px_60px_-30px_rgba(0,0,0,0.3)]"
              >
                <p className="font-mono text-2xl font-semibold text-zinc-200 transition duration-300 group-hover:text-zinc-800">
                  {s.n}
                </p>
                <h3 className="mt-4 text-xl font-semibold tracking-tight">{s.title}</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-zinc-500 transition duration-300 group-hover:text-zinc-700">
                  {s.body}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-14 text-center">
            <Link
              href="/app"
              className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-7 py-3 text-[15px] font-medium text-white transition hover:bg-zinc-700"
            >
              Generate your first script
            </Link>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="border-t border-black/5 bg-white py-24">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-center text-sm font-medium uppercase tracking-widest text-zinc-400">
            Pricing
          </p>
          <h2 className="mx-auto mt-3 max-w-2xl text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Simple, per-slide pricing.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-center text-[15px] text-zinc-500">
            One point per generated slide. Buy points when you need them — no subscription, no
            surprises. You only pay for slides you actually generate.
          </p>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
            {pricing.map((p) =>
              p.free ? (
                <div
                  key="free"
                  className="flex flex-col rounded-3xl border border-dashed border-zinc-300 bg-zinc-50/60 p-6"
                >
                  <p className="text-sm font-medium text-zinc-500">Free preview</p>
                  <p className="mt-2 text-4xl font-semibold tracking-tight">$0</p>
                  <p className="mt-1 text-xs text-zinc-400">2 slides · no card needed</p>
                  <a
                    href="/app"
                    className="mt-5 rounded-full border border-zinc-300 px-4 py-2 text-center text-sm font-medium text-zinc-700 transition hover:bg-white"
                  >
                    Try it
                  </a>
                </div>
              ) : (
                <div
                  key={p.points}
                  className={`relative flex flex-col rounded-3xl border p-6 transition hover:-translate-y-1 hover:shadow-[0_30px_60px_-40px_rgba(0,0,0,0.3)] ${
                    p.featured ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-200/80 bg-white"
                  }`}
                >
                  {p.featured && (
                    <span className="absolute -top-3 left-6 rounded-full bg-white px-3 py-0.5 text-[11px] font-semibold text-zinc-900">
                      Popular
                    </span>
                  )}
                  <p className={`text-sm font-medium ${p.featured ? "text-zinc-300" : "text-zinc-500"}`}>
                    {p.points} points
                  </p>
                  <p className="mt-2 text-4xl font-semibold tracking-tight">${p.usd}</p>
                  <p className="mt-1 text-xs text-zinc-400">≈ ${p.per}/slide · {p.note}</p>
                  <a
                    href="/app"
                    className={`mt-5 rounded-full px-4 py-2 text-center text-sm font-medium transition ${
                      p.featured ? "bg-white text-zinc-900 hover:bg-zinc-100" : "bg-zinc-900 text-white hover:bg-zinc-700"
                    }`}
                  >
                    Buy points
                  </a>
                </div>
              )
            )}
          </div>
          <p className="mt-8 text-center text-xs text-zinc-400">
            Every account can preview one deck of up to two slides free before buying anything.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-black/5 bg-white py-24">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Frequently asked questions
          </h2>
          <p className="mt-3 text-center text-zinc-500">
            Something else on your mind? Reach out from inside the app.
          </p>
          <div className="mt-10 divide-y divide-zinc-100 border-y border-zinc-100">
            {faqs.map((item) => (
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

      {/* Final CTA */}
      <section className="bg-zinc-950 py-20 text-center text-white">
        <h2 className="mx-auto max-w-2xl px-6 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Stop writing scripts the night before.
        </h2>
        <p className="mx-auto mt-4 max-w-xl px-6 text-zinc-400">
          Upload up to two slides free and see the notes written for your moment.
        </p>
        <Link
          href="/app"
          className="mt-8 inline-flex items-center justify-center rounded-full bg-white px-7 py-3 text-[15px] font-medium text-zinc-900 transition hover:bg-zinc-200"
        >
          Start your free trial
        </Link>
      </section>

      <footer className="bg-zinc-950 pb-10 pt-2 text-sm text-zinc-500">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 sm:flex-row">
          <p>NotesBang · tailor-made speaker notes for your moment</p>
          <nav className="flex items-center gap-4 text-xs text-zinc-600">
            <a href="#pricing" className="transition hover:text-zinc-300">Pricing</a>
            <a href="/terms" className="transition hover:text-zinc-300">Terms of use</a>
            <a href="#faq" className="transition hover:text-zinc-300">FAQ</a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
