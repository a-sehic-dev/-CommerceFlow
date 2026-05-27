import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FAQ_ITEMS } from "../config";

function FaqItem({ q, a, open, onToggle }: { q: string; a: string; open: boolean; onToggle: () => void }) {
  return (
    <motion.article
      className={`group overflow-hidden border-b border-white/[0.07] last:border-0 transition ${
        open
          ? "bg-indigo-400/[0.045]"
          : "hover:bg-white/[0.025]"
      }`}
      whileHover={{ backgroundColor: open ? "rgba(129,140,248,0.055)" : "rgba(255,255,255,0.032)" }}
      transition={{ duration: 0.2 }}
    >
      <button
        type="button"
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left sm:px-7 sm:py-4"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span className="text-sm font-semibold tracking-[0.01em] text-[rgba(255,255,255,0.95)] sm:text-[0.98rem]">{q}</span>
        <span
          className={`relative flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-indigo-100 transition ${
            open ? "border-indigo-200/50 bg-indigo-400/14" : "border-white/12 bg-white/[0.035] group-hover:border-indigo-200/35"
          }`}
        >
          <span
            className={`absolute h-0.5 w-3 rounded-full bg-indigo-100 transition-transform ${
              open ? "rotate-180" : ""
            }`}
          />
          <span
            className={`absolute h-3 w-0.5 rounded-full bg-indigo-100 transition-transform ${
              open ? "rotate-90 opacity-0" : "opacity-100"
            }`}
          />
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: "easeInOut" }}
            className="relative overflow-hidden"
          >
            <div className="mx-5 mb-4 border-t border-white/[0.06] pt-3 sm:mx-7">
              <p className="max-w-3xl text-sm leading-6 text-slate-200/92">{a}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}

export function Faq() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="section-pad relative py-12 sm:py-16">
      <div className="pointer-events-none absolute left-1/2 top-10 -z-10 h-56 w-[min(760px,90vw)] -translate-x-1/2 rounded-full bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.14),rgba(37,99,235,0.05)_45%,transparent_72%)] blur-3xl" />
      <div className="mb-7 text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-200/75">Platform Clarity</p>
        <h2 className="mt-3 text-2xl font-bold text-white sm:text-3xl">Frequently asked questions</h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-300">
          Clear answers for teams evaluating CommerceFlow as an operational analytics and reporting workspace.
        </p>
      </div>
      <div className="glass-card mx-auto max-w-3xl overflow-hidden rounded-2xl border-white/[0.09] bg-[#17203b]/78">
        {FAQ_ITEMS.map((item, i) => (
          <FaqItem
            key={item.q}
            q={item.q}
            a={item.a}
            open={openIndex === i}
            onToggle={() => setOpenIndex(openIndex === i ? null : i)}
          />
        ))}
      </div>
    </section>
  );
}
