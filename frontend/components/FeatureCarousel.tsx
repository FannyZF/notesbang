"use client";

import { useState } from "react";

export type Feature = { mark: string; title: string; body: string };

export default function FeatureCarousel({ items }: { items: Feature[] }) {
  const [index, setIndex] = useState(0);
  const count = items.length;
  const prev = () => setIndex((i) => (i - 1 + count) % count);
  const next = () => setIndex((i) => (i + 1) % count);

  return (
    <div className="mx-auto mt-12 max-w-3xl px-6">
      {/* Viewport with sliding track */}
      <div className="overflow-hidden">
        <div
          className="flex transition-transform duration-500 ease-out"
          style={{ transform: `translateX(-${index * 100}%)` }}
        >
          {items.map((f, i) => (
            <article
              key={f.title}
              aria-hidden={i !== index}
              className="w-full shrink-0 px-1 sm:px-6"
            >
              <div className="relative overflow-hidden rounded-3xl border border-zinc-200/80 bg-gradient-to-b from-white to-zinc-50/70 p-8 text-center sm:p-12">
                <div className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-gradient-to-br from-zinc-100 via-white to-transparent" />
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-900 text-lg font-bold text-white">
                  {f.mark}
                </div>
                <h3 className="mt-6 text-2xl font-semibold tracking-tight">{f.title}</h3>
                <p className="mx-auto mt-3 max-w-xl text-[16px] leading-relaxed text-zinc-500">
                  {f.body}
                </p>
                <p className="mt-6 text-xs font-medium tracking-wide text-zinc-300">
                  {String(i + 1).padStart(2, "0")} / {String(count).padStart(2, "0")}
                </p>
              </div>
            </article>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="mt-7 flex items-center justify-center gap-6">
        <button
          type="button"
          aria-label="Previous feature"
          onClick={prev}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-zinc-300 bg-white text-lg text-zinc-600 transition hover:border-zinc-900 hover:text-zinc-900"
        >
          ←
        </button>
        <div className="flex items-center gap-2">
          {items.map((f, i) => (
            <button
              key={f.title}
              type="button"
              aria-label={`Feature ${i + 1}`}
              onClick={() => setIndex(i)}
              className={`h-2 rounded-full transition-all ${
                i === index ? "w-6 bg-zinc-900" : "w-2 bg-zinc-300 hover:bg-zinc-400"
              }`}
            />
          ))}
        </div>
        <button
          type="button"
          aria-label="Next feature"
          onClick={next}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-zinc-300 bg-white text-lg text-zinc-600 transition hover:border-zinc-900 hover:text-zinc-900"
        >
          →
        </button>
      </div>
    </div>
  );
}
