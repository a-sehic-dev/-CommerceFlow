/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        base: "#070b17",
        panel: "#0d1224",
        card: "#121933",
        accent: { DEFAULT: "#6366f1", glow: "#818cf8" },
      },
      boxShadow: {
        glow: "0 0 60px -12px rgba(99, 102, 241, 0.45)",
        card: "0 4px 24px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.06)",
      },
    },
  },
  plugins: [],
};
