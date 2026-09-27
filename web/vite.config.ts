/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build servi par FastAPI sur « / » : chemins relatifs pour les assets.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8765", changeOrigin: false },
    },
  },
  // Application locale servie par FastAPI : un seul lot (~155 ko gzip) est acceptable.
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 800 },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
