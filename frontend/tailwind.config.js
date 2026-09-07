/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    /*
      The type scale REPLACES Tailwind's default rather than extending it.

      That is deliberate. docs/DESIGN.md bans standing small text, and the way
      to make a ban hold is to delete the classes that break it: text-xs and
      text-sm no longer generate anything, so writing one is a visible bug
      rather than a quiet regression. Nothing here is below 16px.

      Chart axis ticks are the one exception and they do not live in Tailwind.
      See src/lib/chartText.ts for that floor and the reasoning.
    */
    fontSize: {
      // The floor. Names a control or a number, never explains one.
      label: ["1rem", { lineHeight: "1.4", fontWeight: "500" }],
      body: ["1.0625rem", { lineHeight: "1.6" }],
      lead: ["1.25rem", { lineHeight: "1.5" }],
      h3: ["1.5rem", { lineHeight: "1.2", letterSpacing: "-0.015em" }],
      h2: ["2rem", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
      stat: ["2.5rem", { lineHeight: "1", letterSpacing: "-0.02em" }],
      h1: ["2.75rem", { lineHeight: "1.05", letterSpacing: "-0.025em" }],
      // clamp() is what keeps 390px working without a responsive variant on
      // every call site.
      hero: ["clamp(2.5rem, 7vw, 4rem)", { lineHeight: "1", letterSpacing: "-0.03em" }],
      mega: ["clamp(3.5rem, 12vw, 7rem)", { lineHeight: "0.9", letterSpacing: "-0.035em" }],
    },
    extend: {
      // Mapped through var() so Tailwind classes and raw CSS resolve to the
      // same custom property. src/index.css is the source of truth.
      colors: {
        squish: {
          50: "var(--squish-50)",
          100: "var(--squish-100)",
          300: "var(--squish-300)",
          500: "var(--squish-500)",
          700: "var(--squish-700)",
        },
        ink: "var(--ink)",
        mist: "var(--mist)",
        alert: "var(--alert)",
        good: "var(--good)",
        squishi: {
          body: "var(--squishi-body)",
          face: "var(--squishi-face)",
          accent: "var(--squishi-accent)",
        },
      },
      fontFamily: {
        display: ["Fraunces Variable", "Georgia", "Times New Roman", "serif"],
        body: [
          "Plus Jakarta Sans Variable",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
      borderRadius: {
        card: "14px",
        panel: "20px",
        pill: "999px",
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
      },
      fontVariantNumeric: {
        tabular: "tabular-nums",
      },
    },
  },
  plugins: [],
};
