import Link from "next/link";
import { Github } from "lucide-react";

const cols = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "/#features" },
      { label: "Architecture", href: "/#architecture" },
      { label: "Cost", href: "/#cost" },
    ],
  },
  {
    title: "Developers",
    links: [
      { label: "Docs", href: "/docs" },
      { label: "GitHub", href: "https://github.com/jyotir07/Loom" },
      { label: "Changelog", href: "https://github.com/jyotir07/Loom/blob/main/CHANGELOG.md" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Roadmap", href: "#" },
      { label: "Stability", href: "#" },
      { label: "Contact", href: "mailto:jyotiraditya.singh.tech@gmail.com" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative border-t border-white/5 mt-10">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10">
          <div className="col-span-2">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-md border border-white/15 bg-gradient-to-br from-electric-500/40 to-violet/40 grid place-items-center">
                <span className="font-mono text-[11px] font-bold tracking-tight">L</span>
              </div>
              <span className="font-semibold">Loom</span>
            </div>
            <p className="mt-4 text-sm text-white/50 max-w-sm leading-relaxed">
              AI infrastructure for engineers. One API across every provider,
              with built-in routing, caching, observability and cost
              optimization.
            </p>
            <Link
              href="https://github.com/jyotir07/Loom"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-6 inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.18em] text-white/40 hover:text-white/80 transition"
            >
              <Github className="h-3.5 w-3.5" />
              jyotir07/Loom
            </Link>
          </div>
          {cols.map((c) => (
            <div key={c.title}>
              <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-white/40">
                {c.title}
              </div>
              <ul className="mt-4 space-y-2.5">
                {c.links.map((l) => (
                  <li key={l.label}>
                    <Link
                      href={l.href}
                      className="text-sm text-white/65 hover:text-white transition-colors"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 pt-6 border-t border-white/5 flex flex-wrap items-center justify-between gap-4 text-xs text-white/35 font-mono">
          <span>© 2026 Loom · AI infrastructure</span>
          <span>v2.0.0 · semver stable · built in Python</span>
        </div>
      </div>
    </footer>
  );
}
