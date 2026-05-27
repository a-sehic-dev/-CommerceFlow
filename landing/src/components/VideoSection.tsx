import { LINKS } from "../config";

export function VideoSection() {
  return (
    <section id="video" className="section-pad py-16 sm:py-24">
      <div className="grid items-center gap-10 lg:grid-cols-2">
        <div>
          <h2 className="text-2xl font-bold text-white sm:text-3xl">See CommerceFlow in Action</h2>
          <p className="mt-4 text-slate-400 leading-relaxed">
            Watch the full workflow: imports, analytics generation, operational alerts, executive dashboards,
            and structured Excel exports — built for teams working from spreadsheet exports today.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-slate-500">
            <li>• CSV/XLSX import pipeline</li>
            <li>• Inventory & profit engines</li>
            <li>• KPI dashboards + charts</li>
            <li>• Enterprise report export</li>
          </ul>
        </div>
        <div className="glass-card overflow-hidden p-2 shadow-glow">
          <div className="aspect-video w-full overflow-hidden rounded-xl bg-black">
            <iframe
              className="h-full w-full"
              src={`${LINKS.youtube}?rel=0&modestbranding=1`}
              title="CommerceFlow platform walkthrough"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          </div>
        </div>
      </div>
    </section>
  );
}
