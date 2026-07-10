"use client";

import { motion } from "framer-motion";
import { providers } from "@/lib/providers";

const visible = providers.slice(0, 6);

const W = 520;
const H = 460;
const CX = W / 2;
const CY = H / 2;
const R = 175;

const nodes = visible.map((p, i) => {
  const angle = (-Math.PI / 2) + (i / visible.length) * Math.PI * 2;
  return {
    p,
    x: CX + Math.cos(angle) * R,
    y: CY + Math.sin(angle) * R,
  };
});

export function RoutingVisualizer() {
  return (
    <div className="relative w-full max-w-[520px] mx-auto aspect-square">
      {/* Background grid mask */}
      <div className="absolute inset-0 bg-grid mask-radial-fade opacity-50" />

      {/* Soft radial glow behind center */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(99,102,241,0.25) 0%, transparent 60%)",
        }}
      />

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="relative w-full h-full"
        fill="none"
        aria-hidden
      >
        <defs>
          <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(99,102,241,0)" />
            <stop offset="50%" stopColor="rgba(139,92,246,0.85)" />
            <stop offset="100%" stopColor="rgba(99,102,241,0)" />
          </linearGradient>
          <linearGradient id="lineStatic" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(255,255,255,0.18)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0.04)" />
          </linearGradient>
          <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(99,102,241,0.8)" />
            <stop offset="100%" stopColor="rgba(99,102,241,0)" />
          </radialGradient>
        </defs>

        {/* Outer dashed orbit */}
        <circle
          cx={CX}
          cy={CY}
          r={R}
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="2 6"
        />

        {/* Static base lines */}
        {nodes.map((n, i) => (
          <line
            key={`base-${i}`}
            x1={CX}
            y1={CY}
            x2={n.x}
            y2={n.y}
            stroke="url(#lineStatic)"
            strokeWidth={1}
          />
        ))}

        {/* Animated traveling lines */}
        {nodes.map((n, i) => (
          <motion.line
            key={`flow-${i}`}
            x1={CX}
            y1={CY}
            x2={n.x}
            y2={n.y}
            stroke={i === 1 ? "#60a5fa" : "url(#lineGradient)"}
            strokeWidth={i === 1 ? 1.5 : 1.2}
            strokeDasharray="6 12"
            initial={{ strokeDashoffset: 0, opacity: 0 }}
            animate={{
              strokeDashoffset: [-0, -72],
              opacity: [0, 1, 1, 0],
            }}
            transition={{
              duration: 2.4,
              repeat: Infinity,
              delay: i * 0.35,
              ease: "linear",
            }}
          />
        ))}

        {/* Selected route highlight */}
        <motion.line
          x1={CX}
          y1={CY}
          x2={nodes[1].x}
          y2={nodes[1].y}
          stroke="#a78bfa"
          strokeWidth={2}
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: [0, 0.9, 0] }}
          transition={{ duration: 1.8, repeat: Infinity, repeatDelay: 1.2 }}
        />

        {/* Center node */}
        <circle cx={CX} cy={CY} r={70} fill="url(#centerGlow)" />
        <circle
          cx={CX}
          cy={CY}
          r={42}
          fill="#0a0b10"
          stroke="rgba(167,139,250,0.5)"
          strokeWidth={1.2}
        />
        <text
          x={CX}
          y={CY - 3}
          textAnchor="middle"
          className="font-mono"
          fontSize={11}
          fill="rgba(255,255,255,0.95)"
        >
          loom
        </text>
        <text
          x={CX}
          y={CY + 12}
          textAnchor="middle"
          className="font-mono"
          fontSize={9}
          fill="rgba(167,139,250,0.85)"
        >
          .generate()
        </text>

        {/* Provider nodes */}
        {nodes.map((n, i) => (
          <g key={`node-${i}`}>
            <motion.circle
              cx={n.x}
              cy={n.y}
              r={28}
              fill="rgba(15, 17, 23, 0.95)"
              stroke={i === 1 ? "#a78bfa" : "rgba(255,255,255,0.15)"}
              strokeWidth={i === 1 ? 1.5 : 1}
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2 + i * 0.08 }}
            />
            <text
              x={n.x}
              y={n.y + 4}
              textAnchor="middle"
              className="font-mono"
              fontSize={10}
              fill={n.p.accent}
              fontWeight={600}
            >
              {n.p.short}
            </text>
          </g>
        ))}

        {/* Tiny moving packets */}
        {nodes.map((n, i) => (
          <motion.circle
            key={`packet-${i}`}
            r={3}
            fill={i === 1 ? "#a78bfa" : "#60a5fa"}
            initial={{ cx: CX, cy: CY, opacity: 0 }}
            animate={{
              cx: [CX, n.x],
              cy: [CY, n.y],
              opacity: [0, 1, 1, 0],
            }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              delay: i * 0.4 + 0.5,
              ease: "easeOut",
            }}
          />
        ))}
      </svg>

      {/* Floating labels */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.2 }}
        className="absolute top-4 right-4 glass rounded-lg px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-white/70"
      >
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 mr-2 animate-pulse-soft" />
        router · health-aware
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.4 }}
        className="absolute bottom-4 left-4 glass rounded-lg px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-white/70"
      >
        p95 · 312ms
      </motion.div>
    </div>
  );
}
