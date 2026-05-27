import { LINKS } from "../config";

export function Footer() {
  return (
    <footer className="section-pad border-t border-white/[0.06] py-12">
      <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="font-bold text-white">CommerceFlow</p>
          <p className="mt-2 text-sm text-slate-500">eCommerce Operations Intelligence</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Founder</p>
          <p className="mt-2 text-sm text-slate-300">Sedin Šehić</p>
          <p className="text-sm text-slate-500">Python Automation Engineer</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Connect</p>
          <div className="mt-2 flex flex-col gap-1 text-sm">
            <a href={LINKS.github} target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
              GitHub
            </a>
            <a href={LINKS.linkedin} target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
              LinkedIn
            </a>
            <a href={`mailto:${LINKS.email}`} className="text-slate-400 transition hover:text-white">
              Contact
            </a>
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email</p>
          <a href={`mailto:${LINKS.email}`} className="mt-2 block whitespace-nowrap text-sm text-indigo-300/90 hover:text-indigo-200">
            {LINKS.email}
          </a>
        </div>
      </div>
      <p className="mt-10 border-t border-white/[0.05] pt-8 text-center text-xs text-slate-600">
        © 2026 CommerceFlow · MIT License · Operational analytics workspace
      </p>
    </footer>
  );
}
