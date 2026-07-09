"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/cn";

const COMMAND = "pip install loom-router";

export function InstallCommand({ className }: { className?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(COMMAND);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard unavailable (insecure context / permissions) — no-op.
    }
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-3 rounded-md border border-white/10 bg-black/40 px-4 py-2.5 font-mono text-[12px]",
        className,
      )}
    >
      <span className="text-white/60">
        <span className="text-white/30 select-none">$ </span>
        {COMMAND}
      </span>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Copied" : "Copy install command"}
        className="text-white/40 hover:text-white transition-colors"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </button>
    </div>
  );
}
