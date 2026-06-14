"use client";

import { motion } from "framer-motion";
import { ArchitectureDiagram } from "@/components/visuals/ArchitectureDiagram";

const points = [
  {
    label: "generate()",
    body: "One contract — sync and async. The model resolves against the catalog, params merge over defaults, and a stable call key is derived for everything downstream.",
  },
  {
    label: "Cache + dedup",
    body: "A cache hit returns instantly. On a miss, single-flight dedup collapses identical in-flight calls onto one upstream request — the rest wait and share the result.",
  },
  {
    label: "Router",
    body: "Picks a candidate and validates the response. On error it fails over to the next provider in order — the caller never sees the retry seam.",
  },
  {
    label: "Adapter",
    body: "The chosen vendor's native SDK, wrapped in retry. Prompt caching, grounding, image polling, and streaming are preserved — not flattened to a lowest common denominator.",
  },
  {
    label: "Response path",
    body: "The result is enriched with usage and cost, written back to cache, and emitted as a structured log to observability — every call, every provider.",
  },
];

export function Architecture() {
  return (
    <section id="architecture" className="relative py-28">
      <div className="absolute inset-0 bg-grid mask-radial-fade opacity-20" />
      <div className="relative mx-auto max-w-7xl px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left column */}
          <div>
            <motion.span
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs font-mono uppercase tracking-[0.18em] text-white/60"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse-soft" />
              Architecture
            </motion.span>
            <motion.h2
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.6 }}
              className="mt-4 text-3xl md:text-5xl font-semibold tracking-tight text-balance text-gradient"
            >
              The path of a single generate() call.
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.6, delay: 0.08 }}
              className="mt-5 text-base text-white/60 leading-relaxed max-w-xl"
            >
              Every request flows the same way — through cache, router, and
              adapter to the upstream vendor, then back with cost and a
              structured log. Optimization happens once, in the middle. New
              providers plug in without touching consuming code.
            </motion.p>

            <div className="mt-10 space-y-5">
              {points.map((p, i) => (
                <motion.div
                  key={p.label}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, margin: "-10%" }}
                  transition={{ duration: 0.5, delay: i * 0.06 }}
                  className="flex gap-4"
                >
                  <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/35 pt-1 w-8">
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div className="flex-1 border-l border-white/10 pl-5">
                    <div className="text-sm font-semibold text-white">
                      {p.label}
                    </div>
                    <div className="mt-1 text-sm text-white/55 leading-relaxed">
                      {p.body}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Right column — diagram */}
          <div className="lg:sticky lg:top-32">
            <ArchitectureDiagram />
          </div>
        </div>
      </div>
    </section>
  );
}
