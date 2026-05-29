import { PREVIEW_ANALYTICS } from "../config";

const CATEGORY_COLORS = [
  "from-indigo-600 to-indigo-400/90",
  "from-violet-600 to-violet-400/90",
  "from-sky-600 to-sky-400/90",
  "from-fuchsia-600 to-fuchsia-400/90",
  "from-cyan-600 to-cyan-400/90",
  "from-slate-600 to-slate-400/90",
] as const;

const RISK_COLORS: Record<string, string> = {
  Low: "bg-emerald-500",
  Medium: "bg-amber-500",
  Critical: "bg-red-500",
};

export function ProductPreview() {
  const a = PREVIEW_ANALYTICS;
  return (
    <section id="demo" className="section-pad py-16 sm:py-20">
      <div className="mb-10 text-center">
        <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Executive workspace preview</h2>
        <p className="mx-auto mt-3 max-w-2xl text-slate-400">
          Live operational analytics from CommerceFlow&apos;s ChronoHaus Watch Co. demo — KPIs, charts,
          alerts, and export-ready reporting at enterprise scale.
        </p>
      </div>
      <div className="glass-card overflow-hidden p-1 shadow-glow">
        <div className="flex items-center gap-2 border-b border-white/[0.06] bg-black/30 px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
          <span className="ml-3 text-xs font-medium text-slate-500">
            CommerceFlow — ChronoHaus Watch Co. · Executive Overview
          </span>
        </div>
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-white/[0.06] bg-gradient-to-b from-[#161922] to-[#0e1016] p-4 ring-1 ring-indigo-500/30">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Total Revenue</p>
            <p className="mt-2 font-mono text-xl font-bold text-white">{a.revenue}</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-gradient-to-b from-[#161922] to-[#0e1016] p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Gross Margin</p>
            <p className="mt-2 font-mono text-xl font-bold text-white">{a.grossMargin}</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-gradient-to-b from-[#161922] to-[#0e1016] p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Inventory Eff.</p>
            <p className="mt-2 font-mono text-xl font-bold text-white">{a.inventoryEfficiency}</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-gradient-to-b from-[#161922] to-[#0e1016] p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Risk Score</p>
            <p className="mt-2 font-mono text-xl font-bold text-white">{a.riskScore}</p>
          </div>
        </div>
        {"deadInventory" in a ? (
          <div className="mx-4 mb-3">
            <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-center">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-red-200/80">Dead Inventory (at cost)</p>
              <p className="mt-1 font-mono text-lg font-bold text-white">{String((a as Record<string, string>).deadInventory)}</p>
            </div>
          </div>
        ) : null}
        <div className="grid gap-2 px-4 pb-3 sm:grid-cols-3">
          <div className="rounded-lg border border-white/[0.05] bg-white/[0.03] px-3 py-2 text-center">
            <p className="font-mono text-sm font-bold text-indigo-200/95">{a.ordersAnalyzed}</p>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Orders analyzed</p>
          </div>
          <div className="rounded-lg border border-white/[0.05] bg-white/[0.03] px-3 py-2 text-center">
            <p className="font-mono text-sm font-bold text-indigo-200/95">{a.activeProducts}</p>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Active products</p>
          </div>
          <div className="rounded-lg border border-white/[0.05] bg-white/[0.03] px-3 py-2 text-center">
            <p className="font-mono text-sm font-bold text-indigo-200/95">{a.operationalAlerts}</p>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Operational alerts</p>
          </div>
        </div>
        <div className="grid gap-3 px-4 pb-4 lg:grid-cols-3">
          <div className="lg:col-span-2 rounded-xl border border-white/[0.06] bg-[#0e1016] p-4">
            <p className="text-xs font-semibold text-slate-400">Revenue Trend · Q1 2026</p>
            <div className="mt-4 flex h-32 items-end gap-1">
              {a.revenueTrendBars.map((h, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-t bg-gradient-to-t from-indigo-600 to-indigo-400/80"
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-[#0e1016] p-4">
            <p className="text-xs font-semibold text-slate-400">Inventory Risk</p>
            <div className="mt-6 space-y-3">
              {a.inventoryRisk.map((b) => (
                <div key={b.label}>
                  <div className="mb-1 flex justify-between text-[10px] text-slate-500">
                    <span>{b.label}</span>
                    <span>{b.pct}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5">
                    <div
                      className={`h-2 rounded-full ${RISK_COLORS[b.label] || "bg-slate-500"}`}
                      style={{ width: `${b.pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mx-4 mb-3 rounded-xl border border-white/[0.06] bg-[#0e1016] p-4">
          <p className="text-xs font-semibold text-slate-400">Category Revenue Mix</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {a.categoryMix.map((c, i) => (
              <div key={c.label} className="flex items-center gap-2">
                <span className="w-20 shrink-0 text-[10px] text-slate-500">{c.label}</span>
                <div className="h-2 flex-1 rounded-full bg-white/5">
                  <div
                    className={`h-2 rounded-full bg-gradient-to-r ${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}`}
                    style={{ width: `${c.pct}%` }}
                  />
                </div>
                <span className="w-8 text-right font-mono text-[10px] text-slate-400">{c.pct}%</span>
              </div>
            ))}
          </div>
        </div>
        <div className="mx-4 mb-4 rounded-xl border border-indigo-400/20 bg-indigo-500/10 px-4 py-2 text-center text-xs text-indigo-100/90">
          Real operational analytics engine · stress-tested with {a.ordersAnalyzed} orders across{" "}
          {a.activeProducts} SKUs
        </div>
      </div>
    </section>
  );
}
