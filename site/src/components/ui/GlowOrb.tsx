import { cn } from "@/lib/cn";

interface GlowOrbProps {
  className?: string;
  color?: "electric" | "violet" | "cyan" | "rose";
  size?: number;
}

const palette: Record<NonNullable<GlowOrbProps["color"]>, string> = {
  electric: "rgba(59, 130, 246, 0.45)",
  violet: "rgba(139, 92, 246, 0.45)",
  cyan: "rgba(34, 211, 238, 0.4)",
  rose: "rgba(244, 63, 94, 0.35)",
};

export function GlowOrb({
  className,
  color = "electric",
  size = 520,
}: GlowOrbProps) {
  return (
    <div
      aria-hidden
      className={cn("glow-orb", className)}
      style={{
        width: size,
        height: size,
        background: `radial-gradient(circle at center, ${palette[color]} 0%, transparent 70%)`,
      }}
    />
  );
}
