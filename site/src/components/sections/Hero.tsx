"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Github, BookOpen, ArrowRight } from "lucide-react";
import { RoutingVisualizer } from "@/components/visuals/RoutingVisualizer";
import { GlowOrb } from "@/components/ui/GlowOrb";

export function Hero() {
  return (
    <section className="relative pt-36 pb-24 md:pt-44 md:pb-32 overflow-hidden">
      {/* Background layers */}
      <div className="absolute inset-0 bg-grid mask-fade-b opacity-60" />
      <GlowOrb className="-top-40 -left-40" color="electric" size={680} />
      <GlowOrb className="-top-20 right-0" color="violet" size={520} />

      <div className="relative mx-auto max-w-7xl px-6 grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] gap-12 items-center">
        {/* Left column */}
        <div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs font-mono uppercase tracking-[0.18em] text-white/60"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-soft" />
            v2.0 · intelligent routing
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.05 }}
            className="mt-6 text-balance text-5xl md:text-6xl lg:text-7xl font-semibold tracking-tight leading-[1.02]"
          >
            <span className="text-gradient">One API for every</span>
            <br />
            <span className="text-gradient-electric">AI provider.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="mt-6 text-balance text-base md:text-lg text-white/65 max-w-xl leading-relaxed"
          >
            Loom unifies AI providers behind a single interface with centralized
            routing, retries, caching, batching, observability, and cost
            optimization — while preserving every vendor&apos;s native capabilities.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25 }}
            className="mt-8 flex flex-wrap items-center gap-3"
          >
            <Link
              href="https://github.com/jyotir07/Loom"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full bg-white text-ink-950 px-5 py-2.5 text-sm font-medium hover:bg-white/90 transition shadow-[0_0_40px_-10px_rgba(255,255,255,0.5)]"
            >
              <Github className="h-4 w-4" />
              View GitHub
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="#dx"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-5 py-2.5 text-sm font-medium text-white hover:bg-white/[0.08] transition"
            >
              <BookOpen className="h-4 w-4" />
              Documentation
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mt-12 flex items-center gap-6 text-[11px] font-mono uppercase tracking-[0.18em] text-white/40"
          >
            <span className="flex items-center gap-2">
              <span className="h-1 w-1 rounded-full bg-electric-400" /> Python
            </span>
            <span className="flex items-center gap-2">
              <span className="h-1 w-1 rounded-full bg-violet-400" /> Sync + Async
            </span>
            <span className="flex items-center gap-2">
              <span className="h-1 w-1 rounded-full bg-emerald-400" /> Apache-2.0
            </span>
          </motion.div>
        </div>

        {/* Right column */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, delay: 0.2 }}
          className="relative"
        >
          <RoutingVisualizer />
        </motion.div>
      </div>
    </section>
  );
}
