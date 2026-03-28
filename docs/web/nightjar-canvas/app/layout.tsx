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

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Nightjar",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Linux, macOS, Windows",
  "programmingLanguage": "Python",
  "softwareVersion": "0.1.0",
  "license": "https://spdx.org/licenses/AGPL-3.0.html",
  "downloadUrl": "https://pypi.org/project/nightjarzzz/",
  "codeRepository": "https://github.com/j4ngzzz/Nightjar",
  "description": "Formal verification pipeline for AI-generated Python code.",
  "url": "https://nightjarcode.dev",
  "offers": {
    "@type": "Offer",
    "price": 0,
    "priceCurrency": "USD",
  },
  "softwareHelp": {
    "@type": "CreativeWork",
    "url": "https://nightjarcode.dev/docs/quickstart",
  },
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
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
          }}
        />
      </head>
      <body className="min-h-full flex flex-col antialiased">
        {children}
      </body>
    </html>
  );
}
