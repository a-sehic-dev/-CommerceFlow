import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/landing/",
  build: {
    outDir: "../static/landing",
    emptyOutDir: true,
  },
});
