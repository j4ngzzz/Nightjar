import type { Metadata, Viewport } from "next";
import { Geist } from "next/font/google";
import { JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Primary UI font — clean, geometric, serious engineering tool
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  weight: ["400", "600"],
  display: "swap",
});

// Monospace for proof identifiers, stage names, code content
const jetBrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Nightjar — Verification Canvas",
  description:
    "Mathematical proof for your code. Not just tested — proven. Nightjar formally verifies your codebase against specs.",
  keywords: ["formal verification", "code proof", "Dafny", "invariants", "nightjar"],
  authors: [{ name: "Nightjar" }],
  openGraph: {
    title: "Nightjar — Verification Canvas",
    description: "Mathematical proof for your code.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0D0B09",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${jetBrainsMono.variable} h-full`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col antialiased">
        {children}
      </body>
    </html>
  );
}
