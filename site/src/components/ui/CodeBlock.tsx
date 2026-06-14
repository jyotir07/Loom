import { codeToHtml } from "shiki";
import { cn } from "@/lib/cn";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  className?: string;
}

export async function CodeBlock({
  code,
  language = "python",
  filename,
  className,
}: CodeBlockProps) {
  const html = await codeToHtml(code, {
    lang: language,
    theme: "github-dark-dimmed",
  });

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-white/10 bg-ink-900/80 backdrop-blur",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-2.5 bg-black/30">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-500/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/70" />
        </div>
        {filename && (
          <span className="text-xs font-mono text-white/40">{filename}</span>
        )}
        <span className="text-xs font-mono uppercase tracking-wider text-white/30">
          {language}
        </span>
      </div>
      <div
        className="px-5 py-5 text-[13px] leading-relaxed font-mono overflow-x-auto scroll-thin [&_pre]:!bg-transparent [&_pre]:!p-0 [&_code]:!bg-transparent"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
