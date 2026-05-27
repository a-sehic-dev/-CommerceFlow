import { FEATURES } from "../config";

export function Features() {
  return (
    <section id="features" className="section-pad py-16 sm:py-24">
      <div className="mb-12 max-w-2xl">
        <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Built for operations & finance teams</h2>
        <p className="mt-3 text-slate-400">
          Deterministic analytics engines — no black-box AI required. Import, analyze, alert, export.
        </p>
      </div>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <article key={f.title} className="glass-card group p-6 transition hover:border-indigo-500/25 hover:shadow-glow">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/15 text-indigo-300 ring-1 ring-indigo-500/20">
              <span className="font-mono text-sm font-bold">◆</span>
            </div>
            <h3 className="text-lg font-semibold text-white">{f.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.desc}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
