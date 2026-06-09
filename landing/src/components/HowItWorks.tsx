const STEPS = [
  {
    n: "01",
    title: "Upload business data",
    desc: "Bring products, sales, and inventory exports into a temporary analytics environment for operational analysis.",
  },
  {
    n: "02",
    title: "Run CommerceFlow analysis",
    desc: "Engines score inventory risk, profit leakage, and product intelligence across your selection.",
  },
  {
    n: "03",
    title: "Explore & export reports",
    desc: "Executive dashboards, alerts, and enterprise Excel workbooks ready for stakeholders.",
  },
];

export function HowItWorks() {
  return (
    <section id="about" className="border-y border-white/[0.06] bg-[#0a0b10] py-16 sm:py-24">
      <div className="section-pad">
        <h2 className="text-center text-2xl font-bold text-white sm:text-3xl">How it works</h2>
        <div className="mt-12 grid gap-8 md:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="relative text-center md:text-left">
              <span className="font-mono text-4xl font-bold text-indigo-500/30">{s.n}</span>
              <h3 className="mt-2 text-lg font-semibold text-white">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
