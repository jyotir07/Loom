import { Navbar } from "@/components/nav/Navbar";
import { Hero } from "@/components/sections/Hero";
import { Metrics } from "@/components/sections/Metrics";
import { Features } from "@/components/sections/Features";
import { Dashboard } from "@/components/sections/Dashboard";
import { Architecture } from "@/components/sections/Architecture";
import { DeveloperExperience } from "@/components/sections/DeveloperExperience";
import { CostOptimization } from "@/components/sections/CostOptimization";
import { CTA } from "@/components/sections/CTA";
import { Footer } from "@/components/sections/Footer";

export default function Home() {
  return (
    <main className="relative">
      <Navbar />
      <Hero />
      <Metrics />
      <Features />
      <Dashboard />
      <Architecture />
      <DeveloperExperience />
      <CostOptimization />
      <CTA />
      <Footer />
    </main>
  );
}
