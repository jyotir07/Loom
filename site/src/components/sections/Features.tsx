"use client";

import { motion } from "framer-motion";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { GlassCard } from "@/components/ui/GlassCard";
import { features } from "@/lib/features";

export function Features() {
  return (
    <section id="features" className="relative py-28">
      <div className="absolute inset-0 bg-grid-fine mask-radial-fade opacity-30" />
      <div className="relative mx-auto max-w-7xl px-6">
        <SectionHeading
          eyebrow="Infrastructure"
          title="Everything you need to run AI in production."
          description="A full stack of infrastructure primitives in one Python package — from intelligent routing to structured outputs. Backward-compatible in v2.0, semver-stable, observable end-to-end."
        />

        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-10%" }}
                transition={{ duration: 0.5, delay: (i % 3) * 0.05 }}
              >
                <GlassCard className="p-6 h-full group">
                  <div className="flex items-start justify-between">
                    <div className="relative">
                      <div className="h-10 w-10 rounded-lg border border-white/10 bg-gradient-to-br from-electric-500/20 to-violet/20 grid place-items-center">
                        <Icon className="h-4.5 w-4.5 text-white/85" strokeWidth={1.5} />
                      </div>
                      <div className="absolute inset-0 rounded-lg bg-electric-500/30 blur-lg opacity-0 group-hover:opacity-50 transition-opacity" />
                    </div>
                    <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/30">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </div>
                  <h3 className="mt-5 text-base font-semibold text-white">
                    {f.title}
                  </h3>
                  <p className="mt-2 text-sm text-white/55 leading-relaxed">
                    {f.body}
                  </p>
                </GlassCard>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
