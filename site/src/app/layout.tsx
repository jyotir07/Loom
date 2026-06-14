import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Loom — One API for every AI provider",
  description:
    "Loom unifies AI providers behind a single interface with centralized routing, retries, caching, batching, observability, and cost optimization.",
  metadataBase: new URL("https://loom.dev"),
  openGraph: {
    title: "Loom — AI infrastructure for production",
    description:
      "One API for every AI provider. Routing, caching, retries, batching, observability, and cost optimization.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="bg-ink-950 text-white font-sans antialiased overflow-x-hidden">
        {children}
      </body>
    </html>
  );
}
