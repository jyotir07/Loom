"use client";

import { motion } from "framer-motion";
import { providers } from "@/lib/providers";

const featured = [
  providers[0], // OpenAI
  providers[1], // Anthropic
  providers[2], // Gemini
  providers[5], // DeepSeek
  providers[4], // Mistral
];

const usage = [82, 64, 47, 38, 26];

export function DashboardBars() {
  return (
    <div className="space-y-3">
      {featured.map((p, i) => (
        <div key={p.key} className="flex items-center gap-3">
          <span className="w-24 text-[11px] font-mono uppercase tracking-wider text-white/50 truncate">
            {p.label}
          </span>
          <div className="flex-1 h-2 rounded-full bg-white/[0.04] overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              whileInView={{ width: `${usage[i]}%` }}
              viewport={{ once: true, margin: "-20%" }}
              transition={{ duration: 0.9, delay: i * 0.08, ease: "easeOut" }}
              className="h-full rounded-full"
              style={{
                background: `linear-gradient(90deg, ${p.accent}99, ${p.accent})`,
                boxShadow: `0 0 18px -4px ${p.accent}`,
              }}
            />
          </div>
          <span className="w-12 text-right text-[11px] font-mono text-white/60">
            {usage[i]}%
          </span>
        </div>
      ))}
    </div>
  );
}
