"use client";

import { motion } from "framer-motion";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { GlassCard } from "@/components/ui/GlassCard";
import { CostChart } from "@/components/visuals/CostChart";
import { costMetrics } from "@/content/metrics";

export function CostOptimization() {
  return (
    <section className="relative py-28">
      <div className="absolute inset-0 bg-grid mask-radial-fade opacity-25" />
      <div className="relative mx-auto max-w-7xl px-6">
        <SectionHeading
          eyebrow="Cost optimization"
          title="Built-in savings on every call."
          description="Response cache, vendor prompt cache, smart routing, and batch APIs — orchestrated automatically. Targets validated in production."
        />

        <div className="mt-16 grid grid-cols-2 lg:grid-cols-4 gap-4">
          {costMetrics.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-15%" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
            >
              <GlassCard className="p-6 h-full">
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/35">
                  {m.label}
                </div>
                <div className="mt-3 text-4xl font-semibold text-emerald-400 tabular-nums">
                  {m.value}
                </div>
                <div className="mt-2 text-xs text-white/50 leading-relaxed">
                  {m.hint}
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>

        {/* Cost chart */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-10%" }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-12"
        >
          <GlassCard className="p-6 md:p-8" hover={false}>
            <div className="flex items-start justify-between mb-6">
              <div>
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">
                  Workload cost · 30 days
                </div>
                <div className="mt-1 text-lg font-semibold text-white">
                  Optimization layer at work
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">
                  Saved
                </div>
                <div className="mt-1 text-2xl font-semibold text-emerald-400 tabular-nums">
                  −58.4%
                </div>
              </div>
            </div>
            <CostChart />
          </GlassCard>
        </motion.div>
      </div>
    </section>
  );
}
