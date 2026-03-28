import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./styles/**/*.css",
    "./*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Amber design system tokens
        "nightjar-bg": "var(--color-bg)",
        "nightjar-bg-raised": "var(--color-bg-raised)",
        "nightjar-border-inactive": "var(--color-border-inactive)",
        "nightjar-border-active": "var(--color-border-active)",
        "nightjar-amber": "var(--color-amber)",
        "nightjar-gold": "var(--color-gold)",
        "nightjar-peak": "var(--color-peak)",
        "nightjar-text-primary": "var(--color-text-primary)",
        "nightjar-text-secondary": "var(--color-text-secondary)",
        "nightjar-error": "var(--color-error)",
        "nightjar-pass": "var(--color-pass)",
        "nightjar-pending": "var(--color-pending)",
        "nightjar-skip": "var(--color-skip)",
        // Semantic aliases
        background: "var(--color-bg)",
        foreground: "var(--color-text-primary)",
        card: {
          DEFAULT: "var(--color-bg-raised)",
          foreground: "var(--color-text-primary)",
        },
        border: "var(--color-border-inactive)",
        ring: "var(--color-amber)",
        primary: {
          DEFAULT: "var(--color-amber)",
          foreground: "var(--color-bg)",
        },
        secondary: {
          DEFAULT: "var(--color-bg-raised)",
          foreground: "var(--color-text-primary)",
        },
        muted: {
          DEFAULT: "var(--color-bg-raised)",
          foreground: "var(--color-text-secondary)",
        },
        accent: {
          DEFAULT: "var(--color-gold)",
          foreground: "var(--color-bg)",
        },
        destructive: {
          DEFAULT: "var(--color-error)",
          foreground: "var(--color-text-primary)",
        },
        popover: {
          DEFAULT: "var(--color-bg-raised)",
          foreground: "var(--color-text-primary)",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "JetBrains Mono", "Consolas", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        // Crystallization animations
        crystallize: {
          "0%": { opacity: "0.5", transform: "scale(0.96)" },
          "60%": { opacity: "0.9", transform: "scale(1.01)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "amber-pulse": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.02)", boxShadow: "0 0 12px rgba(212,146,10,0.4)" },
        },
        "proven-ring": {
          "0%": { opacity: "1", transform: "scale(1)" },
          "100%": { opacity: "0", transform: "scale(2.5)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        crystallize: "crystallize 180ms cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "amber-pulse": "amber-pulse 4s ease-in-out infinite",
        "proven-ring": "proven-ring 1.2s ease-out forwards",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;
