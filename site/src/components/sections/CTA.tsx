"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Github } from "lucide-react";
import { GlowOrb } from "@/components/ui/GlowOrb";

export function CTA() {
  return (
    <section className="relative py-32 overflow-hidden">
      <GlowOrb className="left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2" color="electric" size={760} />
      <GlowOrb className="left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2" color="violet" size={520} />
      <div className="absolute inset-0 bg-grid-fine mask-radial-fade opacity-25" />

      <div className="relative mx-auto max-w-4xl px-6 text-center">
        <motion.h2
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.7 }}
          className="text-balance text-4xl md:text-6xl font-semibold tracking-tight text-gradient"
        >
          Build AI infrastructure once.
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="mt-5 text-base md:text-lg text-white/65 max-w-2xl mx-auto"
        >
          Unify providers, optimize costs, and ship AI products faster. One
          install. Every vendor. Production from day one.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-9 flex flex-wrap items-center justify-center gap-3"
        >
          <Link
            href="https://github.com/jyotir07/Loom"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-white text-ink-950 px-6 py-3 text-sm font-medium hover:bg-white/90 transition shadow-[0_0_60px_-10px_rgba(255,255,255,0.6)]"
          >
            Start Building
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="https://github.com/jyotir07/Loom"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-6 py-3 text-sm font-medium text-white hover:bg-white/[0.08] transition"
          >
            <Github className="h-4 w-4" />
            View GitHub
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="mt-12 inline-block font-mono text-[12px] text-white/40 rounded-md border border-white/10 bg-black/40 px-4 py-2.5"
        >
          <span className="text-white/30 select-none">$ </span>
          pip install loom
        </motion.div>
      </div>
    </section>
  );
}
