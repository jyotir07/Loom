"use client";

import { motion } from "framer-motion";
import { CheckCircle2, AlertTriangle, Activity, ChevronRight } from "lucide-react";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { DashboardChart } from "@/components/visuals/DashboardChart";
import { DashboardBars } from "@/components/visuals/DashboardBars";
import { LiveLogStream } from "@/components/visuals/LiveLogStream";
import { providers } from "@/lib/providers";

const kpis = [
  { label: "Requests / min", value: "12,847", delta: "+8.2%", trend: "up" },
  { label: "P95 latency", value: "312ms", delta: "−14ms", trend: "down" },
  { label: "Cache hit rate", value: "61.4%", delta: "+3.1%", trend: "up" },
  { label: "Cost saved · 24h", value: "$1,284", delta: "+$92", trend: "up" },
];

const health = providers.slice(0, 8).map((p, i) => ({
  ...p,
  status: i === 3 ? "degraded" : "healthy",
  // Deterministic so SSR and client markup match (avoids hydration mismatch).
  latency: 140 + ((i * 67 + 23) % 38) * 10,
}));

export function Dashboard() {
  return (
    <section className="relative py-28">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeading
          eyebrow="Observability"
          title="One control plane for every AI call."
          description="Cost, latency, retries, cache hits, and provider health — captured for every request, surfaced in a single dashboard."
        />

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-5%" }}
          transition={{ duration: 0.7 }}
          className="relative mt-16 rounded-3xl border border-white/10 bg-gradient-to-br from-white/[0.04] to-white/[0.01] backdrop-blur-xl overflow-hidden shadow-[0_0_120px_-30px_rgba(99,102,241,0.45)]"
        >
          {/* Top chrome */}
          <div className="flex items-center justify-between border-b border-white/5 px-5 py-3 bg-black/30">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/70" />
              <div className="ml-4 inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-mono text-white/50">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-soft" />
                loom.dev / observability
              </div>
            </div>
            <div className="hidden md:flex items-center gap-3 text-[11px] font-mono text-white/40">
              <span>last 24h</span>
              <ChevronRight className="h-3 w-3" />
              <span>all providers</span>
            </div>
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-white/5">
            {kpis.map((k) => (
              <div key={k.label} className="bg-ink-900/60 px-5 py-5">
                <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-white/40">
                  {k.label}
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-semibold text-white">
                    {k.value}
                  </span>
                  <span
                    className={`text-xs font-mono ${
                      k.trend === "up" ? "text-emerald-400" : "text-electric-400"
                    }`}
                  >
                    {k.delta}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Main grid */}
          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-px bg-white/5">
            {/* Chart panel */}
            <div className="bg-ink-900/60 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">
                    Requests over time
                  </div>
                  <div className="mt-1 text-sm text-white/80">
                    12,847 / min · 6 providers active
                  </div>
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono text-white/50">
                  <span className="inline-block h-1 w-3 bg-electric-400 rounded-full" />
                  <span>throughput</span>
                </div>
              </div>
              <div className="mt-4 h-44">
                <DashboardChart />
              </div>

              <div className="mt-6 pt-5 border-t border-white/5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 mb-3">
                  Token usage · by provider
                </div>
                <DashboardBars />
              </div>
            </div>

            {/* Provider health + retries */}
            <div className="bg-ink-900/60 p-5">
              <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">
                Provider health
              </div>
              <div className="mt-3 space-y-2.5">
                {health.map((h) => (
                  <div
                    key={h.key}
                    className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.015] px-3 py-2"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          h.status === "healthy"
                            ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
                            : "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
                        } animate-pulse-soft`}
                      />
                      <span className="text-xs text-white/80">{h.label}</span>
                    </div>
                    <div className="flex items-center gap-2 font-mono text-[11px] text-white/40">
                      <span>{h.latency}ms</span>
                      {h.status === "healthy" ? (
                        <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                      ) : (
                        <AlertTriangle className="h-3 w-3 text-amber-400" />
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-5 pt-4 border-t border-white/5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 mb-3">
                  Recent retries · failover
                </div>
                <div className="space-y-2 font-mono text-[11px]">
                  <div className="flex items-center justify-between text-white/55">
                    <span><span className="text-amber-400">retry</span> openai · 429</span>
                    <span>2s ago</span>
                  </div>
                  <div className="flex items-center justify-between text-white/55">
                    <span><span className="text-rose-400">failover</span> openai → anthropic</span>
                    <span>14s ago</span>
                  </div>
                  <div className="flex items-center justify-between text-white/55">
                    <span><span className="text-amber-400">retry</span> mistral · timeout</span>
                    <span>1m ago</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Live log stream */}
          <div className="border-t border-white/5 bg-black/40 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-electric-400" />
                <span className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">
                  Live request log · structured INFO
                </span>
              </div>
              <span className="text-[10px] font-mono text-white/30">
                tailing · 1.3s
              </span>
            </div>
            <LiveLogStream />
          </div>
        </motion.div>
      </div>
    </section>
  );
}
