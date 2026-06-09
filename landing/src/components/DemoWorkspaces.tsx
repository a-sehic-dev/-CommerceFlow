import { DemoLaunchButton } from "./DemoLaunchButton";

export function DemoWorkspaces() {  return (
    <section className="border-y border-white/[0.07] bg-[rgba(17,25,48,0.58)] py-16 sm:py-20">
      <div className="section-pad">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-200/80">Guest Operational Workspace</p>
          <h2 className="mt-4 text-2xl font-bold tracking-tight text-white sm:text-3xl">Temporary analytics environment</h2>
          <p className="mt-4 text-slate-300 leading-relaxed">
            Explore CommerceFlow with realistic operational exports across inventory, products, and sales. The
            workspace opens into dashboards, reporting workflows, inventory intelligence, alerts, and operational
            analytics engines without requiring confidential business files.
          </p>
          <div className="mt-8 grid gap-3 text-left sm:grid-cols-3">
            {[
              "Structured CSV/XLSX imports",
              "Inventory and margin intelligence",
              "Executive reporting workflows",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-white/[0.08] bg-white/[0.04] px-4 py-4 text-sm font-medium text-slate-200">
                {item}
              </div>
            ))}
          </div>
          <div className="mt-8 flex justify-center">
            <DemoLaunchButton className="btn-primary">Explore sample workspace</DemoLaunchButton>
          </div>        </div>
      </div>
    </section>
  );
}
