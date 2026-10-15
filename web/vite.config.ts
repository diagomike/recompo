import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into recomp/static/app and served by `recomp serve`. In development Vite proxies the
// API and media to the studio server so the page has one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/api": { target: "http://127.0.0.1:8770", changeOrigin: false },
      "/media": { target: "http://127.0.0.1:8770", changeOrigin: false },
    },
  },
  build: { outDir: "../recomp/static/app", emptyOutDir: true, chunkSizeWarningLimit: 900 },
});
