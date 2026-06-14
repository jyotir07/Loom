"use client";

import { motion } from "framer-motion";
import { providers } from "@/lib/providers";

/**
 * Connected SVG flow diagram of a generate() call.
 * Hot path: generate() → Cache → Router → Adapter → upstream provider,
 * with the cache-hit short-circuit and router failover branches, and the
 * enriched response travelling back up the left rail to observability.
 * All geometry is deterministic (no Math.random) so SSR markup matches.
 */

const VW = 360;
const VH = 432;

const NODE_W = 160;
const NODE_H = 44;
const NODE_X = 60;
const CX = NODE_X + NODE_W / 2; // 140 — spine centre

const TOP = 20;
const STEP = 84; // node top-to-top spacing
const nodeY = (i: number) => TOP + i * STEP;
const nodeCY = (i: number) => nodeY(i) + NODE_H / 2;

type Tone = "entry" | "hot" | "upstream";

const spine: { title: string; sub: string; tone: Tone }[] = [
  { title: "generate()", sub: "resolve model · merge params", tone: "entry" },
  { title: "Cache", sub: "lookup + single-flight dedup", tone: "hot" },
  { title: "Router", sub: "candidate selection", tone: "hot" },
  { title: "Adapter", sub: "native SDK · wrapped in retry", tone: "hot" },
  { title: "Upstream provider", sub: "OpenAI · Anthropic · Gemini · …", tone: "upstream" },
];

const connectorLabels = ["call key", "miss", "pick", "invoke"];

const branches = [
  { node: 1, label: "hit → cached" },
  { node: 2, label: "error → failover" },
];

const toneFill: Record<Tone, string> = {
  entry: "rgba(96,165,250,0.12)",
  hot: "rgba(139,92,246,0.14)",
  upstream: "rgba(255,255,255,0.035)",
};
const toneStroke: Record<Tone, string> = {
  entry: "rgba(96,165,250,0.5)",
  hot: "rgba(167,139,250,0.55)",
  upstream: "rgba(255,255,255,0.12)",
};

const RAIL_X = 30;
const railTopY = nodeCY(0);
const railBottomY = nodeCY(spine.length - 1);

export function ArchitectureDiagram() {
  return (
    <div className="relative w-full max-w-[520px] mx-auto">
      <svg
        viewBox={`0 0 ${VW} ${VH}`}
        className="w-full h-auto"
        fontFamily="ui-monospace, SFMono-Regular, monospace"
      >
        <defs>
          <marker
            id="ah"
            markerWidth="6"
            markerHeight="6"
            refX="4.5"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L5,3 L0,6 Z" fill="rgba(255,255,255,0.45)" />
          </marker>
          <linearGradient id="hotStroke" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#60a5fa" />
            <stop offset="100%" stopColor="#a78bfa" />
          </linearGradient>
        </defs>

        {/* ---- edges (drawn first, under nodes) ---- */}
        <motion.g
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-10%" }}
          transition={{ duration: 0.6, delay: 0.3 }}
        >
          {/* spine connectors */}
          {connectorLabels.map((label, i) => {
            const y1 = nodeY(i) + NODE_H;
            const y2 = nodeY(i + 1);
            return (
              <g key={label}>
                <line
                  x1={CX}
                  y1={y1}
                  x2={CX}
                  y2={y2 - 2}
                  stroke="rgba(255,255,255,0.18)"
                  strokeWidth={1.25}
                  markerEnd="url(#ah)"
                />
                <text
                  x={CX + 9}
                  y={(y1 + y2) / 2 + 3}
                  fontSize={8.5}
                  fill="rgba(255,255,255,0.42)"
                  letterSpacing="0.5"
                >
                  {label}
                </text>
              </g>
            );
          })}

          {/* branch short-circuits */}
          {branches.map((b) => {
            const cy = nodeCY(b.node);
            return (
              <g key={b.label}>
                <line
                  x1={NODE_X + NODE_W}
                  y1={cy}
                  x2={248 - 2}
                  y2={cy}
                  stroke="rgba(167,139,250,0.4)"
                  strokeWidth={1.1}
                  strokeDasharray="3 3"
                  markerEnd="url(#ah)"
                />
                <rect
                  x={248}
                  y={cy - 13}
                  width={104}
                  height={26}
                  rx={8}
                  fill="rgba(139,92,246,0.08)"
                  stroke="rgba(167,139,250,0.35)"
                />
                <text
                  x={248 + 52}
                  y={cy + 3}
                  fontSize={8.5}
                  fill="rgba(216,205,255,0.85)"
                  textAnchor="middle"
                  letterSpacing="0.4"
                >
                  {b.label}
                </text>
              </g>
            );
          })}

          {/* return rail: enriched response → observability */}
          <path
            d={`M ${NODE_X} ${railBottomY} L ${RAIL_X} ${railBottomY} L ${RAIL_X} ${railTopY} L ${NODE_X - 4} ${railTopY}`}
            fill="none"
            stroke="rgba(96,165,250,0.35)"
            strokeWidth={1.1}
            strokeDasharray="4 4"
            markerEnd="url(#ah)"
          />
          <text
            x={RAIL_X - 11}
            y={(railTopY + railBottomY) / 2}
            fontSize={8}
            fill="rgba(255,255,255,0.4)"
            textAnchor="middle"
            letterSpacing="0.5"
            transform={`rotate(-90 ${RAIL_X - 11} ${(railTopY + railBottomY) / 2})`}
          >
            enrich · cost · structured log
          </text>
        </motion.g>

        {/* ---- flow packet travelling down the spine ---- */}
        <motion.circle
          r={3}
          cx={CX}
          fill="#a78bfa"
          filter="drop-shadow(0 0 4px #a78bfa)"
          initial={{ cy: nodeY(0) + NODE_H, opacity: 0 }}
          animate={{
            cy: [nodeY(0) + NODE_H, nodeCY(spine.length - 1)],
            opacity: [0, 1, 1, 0],
          }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
        />

        {/* ---- nodes ---- */}
        {spine.map((n, i) => (
          <motion.g
            key={n.title}
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-10%" }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
          >
            <rect
              x={NODE_X}
              y={nodeY(i)}
              width={NODE_W}
              height={NODE_H}
              rx={10}
              fill={toneFill[n.tone]}
              stroke={toneStroke[n.tone]}
              strokeWidth={1.25}
            />
            {n.tone === "hot" && (
              <rect
                x={NODE_X}
                y={nodeY(i)}
                width={3}
                height={NODE_H}
                rx={1.5}
                fill="url(#hotStroke)"
              />
            )}
            <text
              x={CX}
              y={nodeY(i) + 19}
              fontSize={12}
              fontWeight={600}
              fill="#ffffff"
              textAnchor="middle"
            >
              {n.title}
            </text>
            <text
              x={CX}
              y={nodeY(i) + 33}
              fontSize={8.5}
              fill="rgba(255,255,255,0.5)"
              textAnchor="middle"
              letterSpacing="0.3"
            >
              {n.sub}
            </text>
          </motion.g>
        ))}
      </svg>

      {/* Upstream providers strip */}
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-10%" }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="mt-4 rounded-xl border border-white/10 bg-black/40 px-4 py-3"
      >
        <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-white/40 mb-2.5">
          Upstream AI providers
        </p>
        <div className="flex flex-wrap gap-1.5">
          {providers.map((p) => (
            <span
              key={p.key}
              className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] font-mono"
              style={{ color: p.accent }}
            >
              {p.label}
            </span>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
