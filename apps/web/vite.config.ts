import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy /api → API lokal, jadi browser memakai satu origin (tanpa CORS).
// API_PROXY_TARGET dapat diubah bila API berjalan di port lain.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
  },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true },
});
