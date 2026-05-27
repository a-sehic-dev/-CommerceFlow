import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { LINKS } from "../config";

type Message = {
  id: string;
  role: "assistant" | "user";
  text: string;
  fallback?: boolean;
};

type AssistantResponse = {
  reply: string;
  configured: boolean;
  fallback: boolean;
  remaining: number;
  support_email: string;
};

type AssistantHistoryMessage = {
  role: "assistant" | "user";
  text: string;
};

const WELCOME =
  "I can help with imports, inventory risk, profit leakage, dashboards, reporting workflows, and operational analytics.";

function sessionId() {
  const key = "cf_assistant_session";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const next = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  localStorage.setItem(key, next);
  return next;
}

function AssistantAvatar({ active = false }: { active?: boolean }) {
  return (
    <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-indigo-300/25 bg-gradient-to-br from-indigo-500/22 to-sky-500/10 text-indigo-50 shadow-[0_10px_32px_rgba(79,70,229,0.22)]">
      {active && <span className="absolute inset-0 rounded-xl border border-indigo-300/40 animate-ping" />}
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 3.75h6M12 3.75v3m-5.25 4.5h10.5m-9 4.5h7.5M5.25 8.25h13.5a1.5 1.5 0 011.5 1.5v7.5a3 3 0 01-3 3H6.75a3 3 0 01-3-3v-7.5a1.5 1.5 0 011.5-1.5z" />
      </svg>
    </div>
  );
}

function LoadingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-indigo-200"
          animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.16 }}
        />
      ))}
    </span>
  );
}

function InlineText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={index} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return <code key={index} className="rounded-md border border-white/10 bg-white/[0.06] px-1.5 py-0.5 font-mono text-[0.86em] text-indigo-100">{part.slice(1, -1)}</code>;
        }
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}

function MarkdownMessage({ text }: { text: string }) {
  const blocks = text.split(/```/g);

  return (
    <div className="space-y-3">
      {blocks.map((block, blockIndex) => {
        if (blockIndex % 2 === 1) {
          return (
            <pre key={blockIndex} className="overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-3 text-xs leading-5 text-slate-100">
              <code>{block.trim()}</code>
            </pre>
          );
        }

        const lines = block.split("\n").filter((line) => line.trim().length > 0);
        const elements: JSX.Element[] = [];
        let listItems: string[] = [];
        let orderedItems: string[] = [];

        const flushLists = () => {
          if (listItems.length) {
            elements.push(
              <ul key={`ul-${blockIndex}-${elements.length}`} className="list-disc space-y-1 pl-5">
                {listItems.map((item, itemIndex) => <li key={itemIndex}><InlineText text={item} /></li>)}
              </ul>
            );
            listItems = [];
          }
          if (orderedItems.length) {
            elements.push(
              <ol key={`ol-${blockIndex}-${elements.length}`} className="list-decimal space-y-1 pl-5">
                {orderedItems.map((item, itemIndex) => <li key={itemIndex}><InlineText text={item} /></li>)}
              </ol>
            );
            orderedItems = [];
          }
        };

        lines.forEach((line) => {
          const trimmed = line.trim();
          if (/^[-*]\s+/.test(trimmed)) {
            orderedItems = [];
            listItems.push(trimmed.replace(/^[-*]\s+/, ""));
            return;
          }
          if (/^\d+\.\s+/.test(trimmed)) {
            listItems = [];
            orderedItems.push(trimmed.replace(/^\d+\.\s+/, ""));
            return;
          }
          flushLists();
          elements.push(
            <p key={`p-${blockIndex}-${elements.length}`} className="leading-6">
              <InlineText text={trimmed} />
            </p>
          );
        });
        flushLists();
        return <div key={blockIndex} className="space-y-3">{elements}</div>;
      })}
    </div>
  );
}

function SupportFallback({ email }: { email: string }) {
  const [copied, setCopied] = useState(false);

  const copyEmail = async () => {
    try {
      await navigator.clipboard.writeText(email);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard can be blocked in some browsers */
    }
  };

  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.04] p-3 text-xs text-slate-300">
      <p className="font-semibold text-white">Need direct assistance?</p>
      <p className="mt-1 font-mono text-indigo-200">{email}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={copyEmail} className="rounded-lg border border-white/10 px-3 py-1.5 font-semibold text-slate-200 transition hover:border-indigo-400/50">
          {copied ? "Copied" : "Copy email"}
        </button>
        <a href={`mailto:${email}?subject=CommerceFlow%20Assistant%20Support`} className="rounded-lg bg-indigo-600 px-3 py-1.5 font-semibold text-white transition hover:bg-indigo-500">
          Open mail
        </a>
      </div>
    </div>
  );
}

export function CommerceFlowAssistant() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [supportEmail, setSupportEmail] = useState(LINKS.email);
  const [messages, setMessages] = useState<Message[]>([
    { id: "welcome", role: "assistant", text: WELCOME },
  ]);
  const session = useMemo(sessionId, []);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    window.requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }, [messages, loading, open]);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMessage: Message = { id: `${Date.now()}-user`, role: "user", text };
    const history: AssistantHistoryMessage[] = messages
      .filter((message) => message.id !== "welcome")
      .slice(-8)
      .map((message) => ({ role: message.role, text: message.text }));
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: session, history }),
      });
      const data = (await response.json()) as AssistantResponse | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in data && data.detail ? data.detail : "Assistant request failed");
      }
      const payload = data as AssistantResponse;
      setRemaining(payload.remaining);
      setSupportEmail(payload.support_email || LINKS.email);
      setMessages((current) => [
        ...current,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          text: payload.reply,
          fallback: payload.fallback || !payload.configured,
        },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Assistant request failed";
      setMessages((current) => [
        ...current,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          text: message,
          fallback: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-50 inline-flex items-center gap-3 rounded-2xl border border-indigo-300/25 bg-[#111a33]/92 px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_46px_rgba(15,23,42,0.55),0_0_38px_rgba(79,70,229,0.16)] backdrop-blur-xl transition hover:border-indigo-200/50 hover:bg-[#17203b]"
        whileHover={{ y: -3, scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
        </span>
        Ask CommerceFlow
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-x-0 bottom-0 z-[80] flex justify-end px-3 pb-3 sm:inset-auto sm:bottom-6 sm:right-6 sm:px-0 sm:pb-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="relative flex h-[min(760px,82vh)] w-full flex-col overflow-hidden rounded-[1.6rem] border border-indigo-200/14 bg-[#0d1428]/96 shadow-[0_35px_120px_rgba(0,0,0,0.46),0_0_70px_rgba(79,70,229,0.14)] backdrop-blur-2xl sm:w-[460px]"
              initial={{ opacity: 0, y: 24, x: 18, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 18, x: 18, scale: 0.96 }}
              transition={{ duration: 0.24 }}
            >
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_0%,rgba(99,102,241,0.20),transparent_36%),radial-gradient(circle_at_5%_90%,rgba(14,165,233,0.11),transparent_38%)]" />
              <motion.div
                className="pointer-events-none absolute -right-10 top-8 h-32 w-32 rounded-full bg-indigo-500/18 blur-3xl"
                animate={{ opacity: [0.35, 0.65, 0.35], scale: [1, 1.08, 1] }}
                transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              />

              <div className="relative flex items-start justify-between border-b border-white/10 px-5 py-4">
                <div className="flex gap-3">
                  <AssistantAvatar active={loading} />
                  <div>
                    <h2 className="text-base font-bold text-white">CommerceFlow AI Copilot</h2>
                    <p className="mt-1 flex items-center gap-2 text-xs text-slate-300">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
                        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
                      </span>
                      Operational intelligence assistant
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
                  aria-label="Close assistant"
                >
                  Minimize
                </button>
              </div>

              <div ref={scrollRef} className="relative flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-5">
                {messages.map((message) => (
                  <motion.div
                    key={message.id}
                    className={`flex gap-3 ${message.role === "user" ? "justify-end" : ""}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    {message.role === "assistant" && <AssistantAvatar />}
                    <div
                      className={`max-w-[84%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                        message.role === "user"
                          ? "rounded-br-md bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-[0_12px_28px_rgba(79,70,229,0.25)]"
                          : "rounded-bl-md border border-indigo-200/12 bg-white/[0.055] text-slate-100 shadow-[0_10px_30px_rgba(2,6,23,0.22)]"
                      }`}
                    >
                      <MarkdownMessage text={message.text} />
                      {message.fallback && <SupportFallback email={supportEmail} />}
                    </div>
                  </motion.div>
                ))}
                {loading && (
                  <div className="flex gap-3">
                    <AssistantAvatar active />
                    <div className="rounded-2xl rounded-bl-md border border-indigo-200/12 bg-white/[0.055] px-4 py-3 text-sm text-slate-200">
                      <span className="mr-3">Thinking through the workflow...</span>
                      <LoadingDots />
                    </div>
                  </div>
                )}
              </div>

              <form onSubmit={send} className="relative border-t border-white/10 bg-[#090f20]/96 p-4">
                <div className="mb-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-[11px] leading-5 text-slate-300">
                  <p className="font-semibold uppercase tracking-[0.16em] text-indigo-200/90">Ask about</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {["imports", "inventory risk", "profit leakage", "dashboards", "operational analytics"].map((topic) => (
                      <span key={topic} className="rounded-full border border-indigo-300/15 bg-indigo-400/10 px-2.5 py-1 text-indigo-100/90">
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="mb-3 flex items-center justify-between text-[11px] text-slate-400">
                  <span>Enter to send · Shift+Enter for new line</span>
                  {remaining !== null && <span>{remaining} questions left this session</span>}
                </div>
                <div className="flex items-end gap-2">
                  <textarea
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={handleInputKeyDown}
                    placeholder="Ask about imports, KPIs, risk, dashboards..."
                    className="max-h-28 min-h-[48px] min-w-0 flex-1 resize-none rounded-2xl border border-white/10 bg-white/[0.055] px-4 py-3 text-sm leading-5 text-white outline-none transition placeholder:text-slate-500 focus:border-indigo-300/70 focus:shadow-[0_0_0_3px_rgba(129,140,248,0.12)]"
                    maxLength={1200}
                    rows={1}
                  />
                  <button
                    type="submit"
                    disabled={loading || !input.trim()}
                    className="rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 px-4 py-3 text-sm font-semibold text-white shadow-[0_12px_28px_rgba(79,70,229,0.25)] transition hover:from-indigo-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.5 4.5 20.5 12 3.5 19.5 6 12zm0 0h7.5" />
                    </svg>
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
