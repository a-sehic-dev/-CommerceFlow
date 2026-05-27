import { motion } from "framer-motion";
import { FOUNDER_BADGES, LINKS } from "../config";

export function Founder() {
  return (
    <section id="founder" className="section-pad py-16 sm:py-24">
      <motion.div
        className="glass-card overflow-hidden p-8 sm:p-10"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-300/80">Founder</p>
        <h2 className="mt-3 text-2xl font-bold text-white sm:text-3xl">Built by Sedin Šehić</h2>
        <p className="mt-2 text-sm font-medium text-slate-300">
          Python Automation Engineer | eCommerce Systems & Operational Analytics
        </p>
        <p className="mt-6 max-w-3xl text-slate-300 leading-relaxed">
          Sedin Šehić is a founder-builder from Bosnia & Herzegovina focused on Python automation, ecommerce
          systems, and operational analytics for teams working with messy exports and fragmented reporting.
        </p>
        <p className="mt-4 max-w-3xl text-slate-300 leading-relaxed">
          With an economics and business operations background, he built CommerceFlow as a practical B2B analytics
          workspace for imports, dashboards, inventory intelligence, reporting workflows, and operational decisions.
        </p>
        <div className="mt-8 flex flex-wrap gap-2">
          {FOUNDER_BADGES.map((b) => (
            <span
              key={b}
              className="rounded-lg border border-white/[0.08] bg-[#121933]/80 px-3 py-1.5 text-xs font-medium text-slate-300"
            >
              {b}
            </span>
          ))}
        </div>
        <div className="mt-8 flex flex-wrap gap-3">
          <a href={LINKS.github} target="_blank" rel="noopener noreferrer" className="btn-secondary">
            GitHub
          </a>
          <a href={LINKS.linkedin} target="_blank" rel="noopener noreferrer" className="btn-secondary">
            LinkedIn
          </a>
          <a href={`mailto:${LINKS.email}?subject=CommerceFlow%20Founder%20Inquiry`} className="btn-primary">
            Contact Founder
          </a>
        </div>
      </motion.div>
    </section>
  );
}
