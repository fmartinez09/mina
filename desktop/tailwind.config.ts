import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--color-canvas) / <alpha-value>)",
        panel: "rgb(var(--color-panel) / <alpha-value>)",
        sidebar: "rgb(var(--color-sidebar) / <alpha-value>)",
        sidebarInk: "rgb(var(--color-sidebar-ink) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        field: "rgb(var(--color-field) / <alpha-value>)",
        hover: "rgb(var(--color-hover) / <alpha-value>)",
        active: "rgb(var(--color-active) / <alpha-value>)",
        composer: "rgb(var(--color-composer) / <alpha-value>)",
        composerLine: "rgb(var(--color-composer-line) / <alpha-value>)",
        user: "rgb(var(--color-user) / <alpha-value>)",
        line: "rgb(var(--color-line) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        brand: "rgb(var(--color-brand) / <alpha-value>)",
        brandStrong: "rgb(var(--color-brand-strong) / <alpha-value>)",
        brandSoft: "rgb(var(--color-brand-soft) / <alpha-value>)",
        warning: "rgb(var(--color-warning) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
      },
      boxShadow: {
        mina: "0 18px 36px rgba(15, 23, 42, 0.10)",
      },
    },
  },
  plugins: [],
} satisfies Config;
