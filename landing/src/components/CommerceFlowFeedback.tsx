import { FormEvent, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

const USEFUL_OPTIONS = [
  "Inventory intelligence",
  "KPI dashboards",
  "Profit leakage detection",
  "Reporting exports",
  "Alerts & recommendations",
] as const;

import { readOrCreateStorageId } from "../utils/storageId";

function guestSessionId() {
  return readOrCreateStorageId("cf_guest_session", "cf-guest");
}

export function CommerceFlowFeedback() {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [useful, setUseful] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const sessionId = useMemo(() => guestSessionId(), []);

  const resetForm = () => {
    setRating(0);
    setUseful([]);
    setText("");
    setEmail("");
    setMessage(null);
    setDone(false);
  };

  const close = () => {
    setOpen(false);
    resetForm();
  };

  const toggleUseful = (value: string) => {
    setUseful((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!rating) {
      setMessage("Choose a rating before submitting.");
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating,
          feedback_text: text.trim() || null,
          email_optional: email.trim() || null,
          session_id: sessionId,
          most_useful: useful,
        }),
      });
      const data = (await response.json()) as { message?: string; detail?: string };
      if (!response.ok) {
        throw new Error(data.detail || data.message || "Could not submit feedback.");
      }
      setDone(true);
      setMessage(data.message || "Feedback captured. Thank you.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not submit feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-5 left-5 z-50 inline-flex items-center gap-2 rounded-full border border-slate-400/20 bg-[#111a33]/92 px-4 py-2.5 text-xs font-bold tracking-wide text-slate-200 shadow-[0_14px_36px_rgba(2,6,23,0.42)] backdrop-blur-xl transition hover:border-indigo-300/35 hover:text-white"
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.98 }}
        aria-label="Share feedback"
        title="Share feedback"
      >
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M7 8h10M7 12h6m-6 4h3M5 6a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H9l-4 3v-3H5a2 2 0 01-2-2V6z"
          />
        </svg>
        Feedback
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[90] flex items-end justify-center p-3 sm:items-center sm:p-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            role="presentation"
          >
            <button
              type="button"
              className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
              aria-label="Close feedback"
              onClick={close}
            />
            <motion.div
              role="dialog"
              aria-labelledby="landing-feedback-title"
              className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-indigo-200/14 bg-[#0d1428] shadow-[0_24px_64px_rgba(0,0,0,0.45)]"
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
            >
              <div className="flex items-start justify-between border-b border-white/10 px-5 py-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-200/80">
                    Quick feedback
                  </p>
                  <h2 id="landing-feedback-title" className="mt-1 text-lg font-bold text-white">
                    How is CommerceFlow for you?
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Optional — app, landing, or product experience. No analysis required.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={close}
                  className="rounded-lg border border-white/10 px-2.5 py-1 text-lg leading-none text-slate-300 hover:bg-white/10 hover:text-white"
                  aria-label="Close"
                >
                  ×
                </button>
              </div>

              <form onSubmit={submit} className="space-y-4 px-5 py-4">
                <div className="flex gap-1" role="radiogroup" aria-label="Rating">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setRating(value)}
                      className={`text-2xl transition ${value <= rating ? "text-amber-300" : "text-slate-600 hover:text-slate-400"}`}
                      aria-label={`${value} star${value > 1 ? "s" : ""}`}
                    >
                      ★
                    </button>
                  ))}
                </div>

                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">What interests you most?</p>
                  <div className="flex flex-wrap gap-2">
                    {USEFUL_OPTIONS.map((option) => (
                      <label
                        key={option}
                        className={`cursor-pointer rounded-full border px-3 py-1.5 text-xs transition ${
                          useful.includes(option)
                            ? "border-indigo-300/40 bg-indigo-500/20 text-indigo-100"
                            : "border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={useful.includes(option)}
                          onChange={() => toggleUseful(option)}
                        />
                        {option}
                      </label>
                    ))}
                  </div>
                </div>

                {rating >= 4 && (
                  <p className="rounded-xl border border-indigo-300/15 bg-indigo-500/10 px-3 py-2 text-xs text-indigo-100/90">
                    Would you like to leave a short testimonial in your message below?
                  </p>
                )}

                <label className="block text-xs font-semibold text-slate-400">
                  Optional feedback
                  <textarea
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    rows={4}
                    maxLength={2000}
                    placeholder="What worked well? What should we improve?"
                    className="mt-1.5 w-full resize-y rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-300/50"
                  />
                </label>

                <label className="block text-xs font-semibold text-slate-400">
                  Email (optional)
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    maxLength={320}
                    placeholder="you@company.com"
                    className="mt-1.5 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-300/50"
                  />
                </label>

                {message && (
                  <p className={`text-sm ${done ? "text-emerald-300" : "text-amber-200"}`}>{message}</p>
                )}

                <div className="flex justify-end gap-2 border-t border-white/10 pt-4">
                  <button
                    type="button"
                    onClick={close}
                    className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-300 hover:bg-white/10"
                  >
                    {done ? "Close" : "Skip"}
                  </button>
                  {!done && (
                    <button
                      type="submit"
                      disabled={submitting || rating < 1}
                      className="rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {submitting ? "Sending…" : "Submit feedback"}
                    </button>
                  )}
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
