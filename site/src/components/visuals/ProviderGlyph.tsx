import { cn } from "@/lib/cn";
import type { Provider } from "@/lib/providers";

interface ProviderGlyphProps {
  provider: Provider;
  size?: number;
  className?: string;
}

export function ProviderGlyph({ provider, size = 36, className }: ProviderGlyphProps) {
  return (
    <div
      className={cn(
        "relative inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] font-mono text-[10px] font-semibold tracking-wider",
        className,
      )}
      style={{
        width: size,
        height: size,
        color: provider.accent,
        boxShadow: `0 0 24px -8px ${provider.accent}55`,
      }}
      title={provider.label}
    >
      {provider.short}
    </div>
  );
}
