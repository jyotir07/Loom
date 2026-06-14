"use client";

import { motion } from "framer-motion";

const W = 700;
const H = 260;

const baselinePts = Array.from({ length: 24 }, (_, i) => ({
  x: (i / 23) * W,
  y: H - (40 + i * 6 + Math.sin(i / 2) * 8),
}));

const optimizedPts = baselinePts.map((p, i) => ({
  x: p.x,
  y: p.y + 60 + i * 1.4,
}));

function toPath(pts: { x: number; y: number }[]) {
  return pts
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");
}

function toArea(pts: { x: number; y: number }[]) {
  return `${toPath(pts)} L ${W} ${H} L 0 ${H} Z`;
}

export function CostChart() {
  return (
    <div className="relative w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="none">
        <defs>
          <linearGradient id="baselineFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(244,63,94,0.18)" />
            <stop offset="100%" stopColor="rgba(244,63,94,0)" />
          </linearGradient>
          <linearGradient id="optimizedFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(52,211,153,0.20)" />
            <stop offset="100%" stopColor="rgba(52,211,153,0)" />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75].map((g) => (
          <line
            key={g}
            x1={0}
            x2={W}
            y1={H * g}
            y2={H * g}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="3 6"
          />
        ))}

        {/* Baseline cost (without Loom) */}
        <motion.path
          d={toArea(baselinePts)}
          fill="url(#baselineFill)"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
        />
        <motion.path
          d={toPath(baselinePts)}
          fill="none"
          stroke="rgba(244,63,94,0.8)"
          strokeWidth={1.4}
          strokeDasharray="6 4"
          initial={{ pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1.6, ease: "easeOut" }}
        />

        {/* Optimized cost (with Loom) */}
        <motion.path
          d={toArea(optimizedPts)}
          fill="url(#optimizedFill)"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: 0.6 }}
        />
        <motion.path
          d={toPath(optimizedPts)}
          fill="none"
          stroke="rgba(52,211,153,0.95)"
          strokeWidth={1.8}
          initial={{ pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1.6, delay: 0.6, ease: "easeOut" }}
        />
      </svg>

      <div className="absolute top-2 right-3 flex items-center gap-4 text-[11px] font-mono uppercase tracking-wider">
        <span className="flex items-center gap-2 text-rose-400">
          <span className="inline-block h-px w-5 bg-rose-400/80 border-dashed" />
          Baseline
        </span>
        <span className="flex items-center gap-2 text-emerald-400">
          <span className="inline-block h-px w-5 bg-emerald-400/80" />
          With Loom
        </span>
      </div>
    </div>
  );
}
