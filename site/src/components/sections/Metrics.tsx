"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/GlassCard";
import { trustMetrics } from "@/content/metrics";

export function Metrics() {
  return (
    <section className="relative py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {trustMetrics.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-15%" }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
            >
              <GlassCard className="p-6 h-full group">
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40">
                  {String(i + 1).padStart(2, "0")} ·
                  <span className="ml-1">metric</span>
                </div>
                <div className="mt-3 text-3xl md:text-4xl font-semibold text-gradient-electric">
                  {m.value}
                </div>
                <div className="mt-1 text-sm font-medium text-white">
                  {m.label}
                </div>
                <div className="mt-2 text-xs text-white/45 leading-relaxed">
                  {m.hint}
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
