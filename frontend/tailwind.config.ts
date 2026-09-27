import type { Config } from "tailwindcss";

/**
 * The palette is declared once in `app/globals.css` as CSS custom properties and referenced
 * here, so a colour can never drift between a utility class and a component style.
 *
 * The names are epistemic, not visual: `fact`, `inference`, `assumption`, `conflict`. Using
 * `amber` or `blue` here would let a future component reach for a colour because it looks
 * right, which is exactly how a semantic palette stops being semantic.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        raised: "var(--bg-raised)",
        panel: "var(--bg-panel)",
        hover: "var(--bg-hover)",
        line: "var(--border)",
        "line-strong": "var(--border-strong)",

        ink: "var(--text)",
        "ink-2": "var(--text-secondary)",
        "ink-3": "var(--text-tertiary)",
        "ink-4": "var(--text-faint)",

        paper: "var(--paper)",
        "paper-dim": "var(--paper-dim)",
        "paper-ink": "var(--paper-text)",
        "paper-muted": "var(--paper-muted)",

        fact: "var(--fact)",
        inference: "var(--inference)",
        assumption: "var(--assumption)",
        recommendation: "var(--recommendation)",
        conflict: "var(--conflict)",
        unreadable: "var(--unreadable)",
      },
      fontFamily: {
        sans: ["var(--font-ui)"],
        mono: ["var(--font-mono)"],
        source: ["var(--font-source)"],
      },
      maxWidth: {
        content: "1400px",
      },
      spacing: {
        13: "3.25rem",
      },
    },
  },
  plugins: [],
};

export default config;
