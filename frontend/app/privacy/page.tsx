import type { ReactNode } from "react";

export default function PrivacyPage() {
  return (
    <main className="min-h-full bg-white font-sans text-zinc-900 antialiased">
      <header className="sticky top-0 z-20 border-b border-black/5 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between px-6">
          <a href="/" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 text-sm font-bold text-white">
              NB
            </span>
            NotesBang
          </a>
          <a href="/app" className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-zinc-700">
            Open the app
          </a>
        </div>
      </header>

      <article className="mx-auto max-w-3xl px-6 py-14">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">Legal</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Privacy Policy</h1>
        <p className="mt-2 text-sm text-zinc-400">Last updated: 2026-09-09 · NotesBang</p>

        <div className="mt-8 space-y-6 text-[15px] leading-relaxed text-zinc-600">
          <Section title="1. What we collect">
            Account data (your email), the presentations you upload, the speaker notes
            we generate, optional speaking-pace recordings used only to measure your
            pace, style samples you provide, and billing/usage records.
          </Section>
          <Section title="2. How we use it">
            To parse your slides, generate and refine speaker notes, measure your pace,
            operate billing, prevent abuse, and support you. We do not sell your data.
          </Section>
          <Section title="3. AI processing">
            To write notes, your document content (and, for chart/key slides, rendered
            page images when enabled) is sent to a third-party AI model provider for
            processing. We only send what is needed for the requested feature.
          </Section>
          <Section title="4. Storage & retention">
            Uploads and generated output are stored on our infrastructure and deleted
            when you delete a project or your account. Temporary artifacts (page
            images, exports, pace recordings) are purged on a retention schedule.
          </Section>
          <Section title="5. Cookies">
            We use essential cookies/session tokens to keep you signed in. We do not
            use third-party advertising cookies.
          </Section>
          <Section title="6. Your rights">
            You can access and correct your data, export it, and delete your account at
            any time from the app (Account security). Where GDPR/CCPA apply, you have
            the right to access, portability, erasure, and to object to processing.
          </Section>
          <Section title="7. Security">
            We use encryption in transit, access controls, and least-privilege practices.
            No system is perfectly secure; we work to protect your data and to notify
            you of material incidents as required by law.
          </Section>
          <Section title="8. Contact">
            Privacy requests: reach us from inside the product. A dedicated privacy
            contact and data-processing details will be finalized before public launch.
          </Section>
        </div>
      </article>
    </main>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-[17px] font-semibold text-zinc-900">{title}</h2>
      <p className="mt-1.5">{children}</p>
    </section>
  );
}
