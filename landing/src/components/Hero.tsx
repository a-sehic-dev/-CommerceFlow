import { LINKS, TRUST_TAGS } from "../config";

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-16 sm:pt-40 sm:pb-24">
      <div className="section-pad relative">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-300/90">
          B2B Operational Intelligence
        </p>
        <h1 className="max-w-4xl text-4xl font-bold leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-[3.25rem]">
          eCommerce Intelligence Platform for Operational Decision-Making
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-400">
          CommerceFlow transforms raw inventory, sales, and operational exports into executive dashboards,
          inventory intelligence, analytics pipelines, and structured business insights.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <a href="/dashboard" className="btn-primary">
            Run Analysis
          </a>
          <a href={LINKS.youtubeWatch} target="_blank" rel="noopener noreferrer" className="btn-secondary">
            Watch Platform Walkthrough
          </a>
        </div>
        <div className="mt-10 flex flex-wrap gap-2">
          {TRUST_TAGS.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-white/[0.08] bg-[#121933]/60 px-3 py-1 text-xs font-medium text-slate-400"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
