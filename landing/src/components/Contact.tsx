import { motion } from "framer-motion";
import { LINKS } from "../config";

export function Contact() {
  return (
    <section id="contact" className="section-pad py-16 sm:py-20">
      <div className="glass-card mx-auto max-w-2xl p-8 text-center sm:p-10">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-300 ring-1 ring-indigo-500/25">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-white sm:text-2xl">Enterprise & Collaboration Inquiries</h2>
        <p className="mt-4 text-sm text-slate-400 leading-relaxed">
          Interested in operational analytics systems, custom ecommerce intelligence workflows, or business
          automation solutions?
        </p>
        <motion.a
          href={`mailto:${LINKS.email}?subject=CommerceFlow%20Founder%20Inquiry`}
          className="mt-6 inline-block font-mono text-base text-indigo-200 transition hover:text-white"
          whileHover={{ scale: 1.02 }}
        >
          {LINKS.email}
        </motion.a>
        <div className="mt-6">
          <a href={`mailto:${LINKS.email}?subject=CommerceFlow%20Founder%20Inquiry`} className="btn-primary text-sm">
            Contact Founder
          </a>
        </div>
      </div>
    </section>
  );
}
