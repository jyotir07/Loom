"use client";

import Link from "next/link";
import { easeInOut, motion, useScroll, useTransform } from "framer-motion";
import { useState, useEffect } from "react";
import { Github, ArrowUpRight, Menu, X } from "lucide-react";

const links = [
  { href: "/#features", label: "Features" },
  { href: "/#architecture", label: "Architecture" },
  { href: "/docs", label: "Docs" },
  {
    href: "https://pypi.org/project/loom-router/",
    label: "PyPI",
    external: true,
  },
  {
    href: "https://github.com/jyotir07/Loom",
    label: "GitHub",
    external: true,
  },
];

export function Navbar() {
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Morph progress is locked directly to scroll position (no spring / no time
  // lag): as you scroll down from the hero the bar shrinks in real time, and
  // grows back on scroll up. The easing is applied to position, not time, so
  // the shrink curve stays smooth without introducing any delay.
  const morph = useTransform(scrollY, [0, 120], [0, 1], {
    clamp: true,
    ease: easeInOut,
  });

  const width = useTransform(morph, [0, 1], ["100%", "min(880px, 92%)"]);
  const radius = useTransform(morph, [0, 1], [0, 999]);
  const padding = useTransform(morph, [0, 1], ["1rem 1.5rem", "0.65rem 1rem"]);
  const blur = useTransform(morph, [0, 1], [0, 18]);
  const backdropFilter = useTransform(blur, (b) => `blur(${b}px)`);
  const bg = useTransform(
    morph,
    [0, 1],
    ["rgba(5,6,10,0)", "rgba(15,17,23,0.72)"],
  );
  const border = useTransform(
    morph,
    [0, 1],
    ["rgba(255,255,255,0)", "rgba(255,255,255,0.08)"],
  );

  useEffect(() => {
    const unsub = scrollY.on("change", (y) => setScrolled(y > 60));
    return unsub;
  }, [scrollY]);

  return (
    <div className="fixed inset-x-0 top-0 z-50 flex justify-center pointer-events-none">
      <motion.nav
        style={{
          width,
          borderRadius: radius,
          padding,
          backdropFilter,
          background: bg,
          borderColor: border,
        }}
        className="pointer-events-auto mt-3 flex items-center justify-between border"
      >
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="relative">
            <div className="h-7 w-7 rounded-md border border-white/15 bg-gradient-to-br from-electric-500/40 to-violet/40 grid place-items-center">
              <span className="font-mono text-[11px] font-bold tracking-tight">L</span>
            </div>
            <div className="absolute inset-0 rounded-md bg-electric-500/40 blur-md opacity-0 group-hover:opacity-60 transition-opacity" />
          </div>
          <span className="font-semibold tracking-tight">Loom</span>
          <span className="hidden md:inline text-[10px] font-mono uppercase tracking-[0.2em] text-white/40 ml-1">
            Infrastructure
          </span>
        </Link>

        <div className="hidden md:flex items-center gap-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              target={l.external ? "_blank" : undefined}
              rel={l.external ? "noopener noreferrer" : undefined}
              className="px-3 py-1.5 text-sm text-white/65 hover:text-white transition-colors rounded-full"
            >
              {l.label}
            </Link>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-2">
          <Link
            href="https://github.com/jyotir07/Loom"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-white text-ink-950 px-4 py-1.5 text-sm font-medium hover:bg-white/90 transition-colors"
          >
            Get Started
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <button
          onClick={() => setMobileOpen((s) => !s)}
          className="md:hidden p-1.5 rounded-md border border-white/10 text-white/80"
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </motion.nav>

      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="md:hidden absolute top-20 left-4 right-4 glass-strong rounded-2xl p-4 pointer-events-auto"
        >
          <div className="flex flex-col gap-1">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                target={l.external ? "_blank" : undefined}
                rel={l.external ? "noopener noreferrer" : undefined}
                onClick={() => setMobileOpen(false)}
                className="px-3 py-2 rounded-lg text-sm text-white/80 hover:bg-white/5"
              >
                {l.label}
              </Link>
            ))}
            <Link
              href="https://github.com/jyotir07/Loom"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setMobileOpen(false)}
              className="mt-2 inline-flex items-center justify-center gap-2 rounded-full bg-white text-ink-950 px-4 py-2 text-sm font-medium"
            >
              <Github className="h-4 w-4" /> Get Started
            </Link>
          </div>
        </motion.div>
      )}
    </div>
  );
}
