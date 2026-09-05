/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // REST goes to FastAPI. The websocket route needs ws: true so the
      // upgrade handshake is forwarded rather than answered by Vite.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  test: {
    // Components need a DOM. tokens.test.ts reads files from disk instead and
    // opts back out with a @vitest-environment docblock.
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    css: false,
  },
});
