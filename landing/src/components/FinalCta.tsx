import { LINKS } from "../config";
import { DemoLaunchButton } from "./DemoLaunchButton";
import { Footer } from "./Footer";
export function FinalCta() {
  return (
    <section className="section-pad pt-8 pb-0">
      <div className="relative overflow-hidden rounded-3xl border border-indigo-500/20 bg-gradient-to-br from-[#121933] via-[#0d1224] to-[#070b17] px-8 py-14 text-center shadow-glow sm:px-16">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.12),transparent_65%)]" />
        <h2 className="relative text-2xl font-bold text-white sm:text-4xl">
          Turn messy eCommerce exports into operational intelligence.
        </h2>
        <div className="relative mt-8 flex flex-wrap justify-center gap-4">
          <DemoLaunchButton className="btn-primary">Try guest demo</DemoLaunchButton>
          <a href={LINKS.repo} target="_blank" rel="noopener noreferrer" className="btn-secondary">
            View GitHub
          </a>
        </div>      </div>
      <Footer />
    </section>
  );
}
