import { SectionHeading } from "@/components/ui/SectionHeading";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { codeSamples } from "@/lib/code-samples";

export function DeveloperExperience() {
  return (
    <section id="dx" className="relative py-28">
      <div className="absolute inset-0 bg-grid-fine mask-radial-fade opacity-25" />
      <div className="relative mx-auto max-w-7xl px-6">
        <SectionHeading
          eyebrow="Developer experience"
          title="Designed for engineers who ship."
          description="State intent, not a vendor. The same generate() call routes to the right provider, falls back on failure, and can return a validated object — with usage and cost on every response."
        />

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-5">
          {codeSamples.slice(0, 2).map((sample) => (
            <div key={sample.id}>
              <div className="mb-3 flex items-center gap-2">
                <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-mono text-electric-400">
                  loom.{sample.id}
                </span>
                <span className="text-[11px] font-mono uppercase tracking-wider text-white/35">
                  {sample.label}
                </span>
              </div>
              <CodeBlock
                code={sample.code}
                language="python"
                filename={sample.filename}
              />
            </div>
          ))}
        </div>

        <div className="mt-5 grid grid-cols-1 lg:grid-cols-3 gap-5">
          {codeSamples.slice(2).map((sample) => (
            <div key={sample.id}>
              <div className="mb-3 flex items-center gap-2">
                <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-mono text-violet-400">
                  {sample.label}
                </span>
              </div>
              <CodeBlock
                code={sample.code}
                language="python"
                filename={sample.filename}
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
