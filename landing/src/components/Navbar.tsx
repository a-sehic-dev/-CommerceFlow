import { LINKS } from "../config";

import { LoginMenu } from "./LoginMenu";

import { Logo } from "./Logo";



const NAV = [

  { href: "#about", label: "About" },

  { href: "#features", label: "Features" },

  { href: "#demo", label: "Workspace" },

  { href: "#video", label: "Video" },

  { href: "#faq", label: "FAQ" },

];



export function Navbar() {

  return (

    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/[0.08] bg-[rgba(11,16,32,0.86)] backdrop-blur-xl">

      <div className="section-pad flex h-[4.25rem] items-center justify-between gap-4 sm:h-[4.5rem]">

        <a href="/" className="flex min-w-0 items-center gap-3 text-white no-underline">

          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-glow">

            <Logo className="h-5 w-5" />

          </span>

          <span className="min-w-0 leading-tight">

            <span className="block text-lg font-bold tracking-tight text-white">CommerceFlow</span>

            <span className="block truncate text-[10px] font-medium uppercase tracking-[0.14em] text-slate-300 sm:text-[11px]">

              eCommerce Operations Intelligence

            </span>

          </span>

        </a>

        <nav className="hidden items-center gap-6 lg:flex xl:gap-7">

          {NAV.map((n) => (

            <a key={n.href} href={n.href} className="text-sm font-medium text-slate-400 transition hover:text-white">

              {n.label}

            </a>

          ))}

          <a href={LINKS.github} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-slate-400 transition hover:text-white">

            GitHub

          </a>

          <a href={LINKS.linkedin} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-slate-400 transition hover:text-white">

            LinkedIn

          </a>

        </nav>

        <LoginMenu />

      </div>

    </header>

  );

}

