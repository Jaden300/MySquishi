/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
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
      },
      borderRadius: {
        card: "12px",
        panel: "16px",
      },
      fontVariantNumeric: {
        tabular: "tabular-nums",
      },
    },
  },
  plugins: [],
};
