"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

const W = 600;
const H = 200;
const N = 48;

// Deterministic seed shared by server and client to avoid hydration mismatch.
// Real (random) data is swapped in after mount inside useEffect.
const SEED: number[] = Array.from({ length: N }, (_, i) =>
  Math.max(0.15, Math.min(0.92, 0.55 + 0.2 * Math.sin(i / 3) + 0.1 * Math.sin(i / 1.7))),
);

function seedSeries(): number[] {
  const arr: number[] = [];
  let v = 0.55;
  for (let i = 0; i < N; i++) {
    v += (Math.random() - 0.5) * 0.12;
    v = Math.max(0.15, Math.min(0.92, v));
    arr.push(v);
  }
  return arr;
}

function toPath(series: number[]): string {
  return series
    .map((v, i) => {
      const x = (i / (N - 1)) * W;
      const y = H - v * (H - 20) - 10;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

function toArea(series: number[]): string {
  const top = toPath(series);
  return `${top} L ${W} ${H} L 0 ${H} Z`;
}

export function DashboardChart() {
  const [series, setSeries] = useState<number[]>(SEED);

  useEffect(() => {
    // Swap the deterministic seed for randomized data once on the client.
    setSeries(seedSeries());
    const id = setInterval(() => {
      setSeries((prev) => {
        const next = prev.slice(1);
        let last = prev[prev.length - 1] + (Math.random() - 0.5) * 0.12;
        last = Math.max(0.15, Math.min(0.92, last));
        next.push(last);
        return next;
      });
    }, 1500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="relative w-full h-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(99,102,241,0.35)" />
            <stop offset="100%" stopColor="rgba(99,102,241,0)" />
          </linearGradient>
          <linearGradient id="chartStroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#60a5fa" />
            <stop offset="100%" stopColor="#a78bfa" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((g) => (
          <line
            key={g}
            x1={0}
            x2={W}
            y1={H - g * (H - 20) - 10}
            y2={H - g * (H - 20) - 10}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="3 6"
          />
        ))}

        <motion.path
          d={toArea(series)}
          fill="url(#chartArea)"
          animate={{ d: toArea(series) }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
        <motion.path
          d={toPath(series)}
          fill="none"
          stroke="url(#chartStroke)"
          strokeWidth={1.5}
          animate={{ d: toPath(series) }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />

        {/* Cursor dot at the end */}
        <motion.circle
          r={3}
          fill="#a78bfa"
          animate={{
            cx: W,
            cy: H - series[series.length - 1] * (H - 20) - 10,
          }}
          transition={{ duration: 0.6 }}
        />
      </svg>
    </div>
  );
}
