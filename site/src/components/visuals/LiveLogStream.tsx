"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface LogLine {
  id: number;
  provider: string;
  model: string;
  latency: number;
  cached: boolean;
  cost: string;
  status: "ok" | "retry" | "failover";
  time: string;
}

const providersPool = [
  { provider: "openai", model: "gpt-4o-mini" },
  { provider: "anthropic", model: "claude-haiku-4-5" },
  { provider: "gemini", model: "gemini-2.5-flash" },
  { provider: "deepseek", model: "deepseek-v3" },
  { provider: "openai", model: "gpt-4o" },
  { provider: "mistral", model: "mistral-large" },
];

function generate(id: number): LogLine {
  const p = providersPool[Math.floor(Math.random() * providersPool.length)];
  const r = Math.random();
  const status: LogLine["status"] = r < 0.05 ? "failover" : r < 0.12 ? "retry" : "ok";
  const cached = Math.random() < 0.4;
  const latency = +(80 + Math.random() * 480).toFixed(1);
  const cost = (Math.random() * 0.0002).toFixed(7);
  const time = new Date().toISOString().slice(11, 19);
  return { id, ...p, latency, cached, cost, status, time };
}

// Deterministic seed rendered identically on server and client. Replaced with
// live random data after mount (see useEffect) to avoid hydration mismatch.
const SEED_LOGS: LogLine[] = Array.from({ length: 6 }, (_, i) => {
  const p = providersPool[i % providersPool.length];
  return {
    id: i,
    ...p,
    latency: 120 + i * 47,
    cached: i % 3 === 0,
    cost: `0.000${(120 + i * 7).toString().padStart(4, "0")}`,
    status: i === 2 ? "retry" : "ok",
    time: "--:--:--",
  };
});

const colorByStatus: Record<LogLine["status"], string> = {
  ok: "text-emerald-400",
  retry: "text-amber-400",
  failover: "text-rose-400",
};

export function LiveLogStream() {
  const [logs, setLogs] = useState<LogLine[]>(SEED_LOGS);

  useEffect(() => {
    // Swap the deterministic seed for live random data once on the client.
    setLogs(Array.from({ length: 6 }, (_, i) => generate(i)));
    let id = 6;
    const interval = setInterval(() => {
      setLogs((prev) => {
        const next = [...prev, generate(id++)];
        return next.slice(-7);
      });
    }, 1300);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="font-mono text-[11px] leading-[1.55] space-y-1 min-h-[180px]">
      <AnimatePresence initial={false}>
        {logs.map((log) => (
          <motion.div
            key={log.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="flex items-center gap-3 whitespace-nowrap"
          >
            <span className="text-white/30">{log.time}</span>
            <span className={colorByStatus[log.status]}>{log.status.padEnd(8)}</span>
            <span className="text-white/70 w-20">{log.provider}</span>
            <span className="text-white/50 w-32 truncate">{log.model}</span>
            <span className="text-white/40">
              {log.latency.toFixed(1)}<span className="text-white/30">ms</span>
            </span>
            {log.cached && (
              <span className="rounded-md border border-violet-400/40 bg-violet-400/10 px-1.5 py-px text-[10px] text-violet-300">
                cached
              </span>
            )}
            <span className="text-white/30 ml-auto">${log.cost}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
