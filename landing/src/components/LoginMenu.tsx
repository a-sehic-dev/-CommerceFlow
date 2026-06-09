import { useEffect, useRef, useState } from "react";
import { LINKS } from "../config";
import { useDemoLaunch } from "../context/DemoLaunchContext";

export function LoginMenu() {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { startDemo } = useDemoLaunch();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        className="btn-primary text-xs sm:text-sm"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((current) => !current)}
      >
        Login
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-xl border border-white/10 bg-[#121933]/95 py-1 shadow-[0_18px_46px_rgba(15,23,42,0.55)] backdrop-blur-xl"
        >
          <a
            href={LINKS.login}
            role="menuitem"
            className="block px-4 py-2.5 text-sm font-medium text-slate-100 transition hover:bg-white/5"
            onClick={() => setOpen(false)}
          >
            Sign in
          </a>
          <button
            type="button"
            role="menuitem"
            className="block w-full px-4 py-2.5 text-left text-sm font-medium text-slate-100 transition hover:bg-white/5"
            onClick={() => {
              setOpen(false);
              startDemo();
            }}
          >
            Guest demo
          </button>
        </div>
      )}
    </div>
  );
}
