import { cn } from "@/lib/cn";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  strong?: boolean;
}

export function GlassCard({
  className,
  hover = true,
  strong = false,
  children,
  ...rest
}: GlassCardProps) {
  return (
    <div
      className={cn(
        "relative rounded-2xl",
        strong ? "glass-strong" : "glass",
        "transition-all duration-300",
        hover &&
          "hover:border-white/15 hover:shadow-[0_0_0_1px_rgba(99,102,241,0.18),0_30px_80px_-20px_rgba(99,102,241,0.25)]",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
