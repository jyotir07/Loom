import Link from "next/link";
import { cn } from "@/lib/cn";

interface ButtonProps {
  href: string;
  variant?: "primary" | "ghost" | "secondary";
  className?: string;
  external?: boolean;
  children: React.ReactNode;
}

export function Button({
  href,
  variant = "primary",
  className,
  external,
  children,
}: ButtonProps) {
  const styles =
    variant === "primary"
      ? "bg-white text-ink-950 hover:bg-white/90 shadow-[0_0_30px_-5px_rgba(255,255,255,0.4)]"
      : variant === "secondary"
        ? "bg-white/[0.06] text-white border border-white/15 hover:bg-white/[0.1] hover:border-white/25"
        : "bg-transparent text-white/80 hover:text-white";

  const className_ = cn(
    "inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all duration-200",
    styles,
    className,
  );

  const props = external
    ? { target: "_blank", rel: "noopener noreferrer" }
    : {};

  return (
    <Link href={href} className={className_} {...props}>
      {children}
    </Link>
  );
}
