import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";


// The dev server proxies /v1 and /health to the Device Gateway so the browser
// stays same-origin during development; `SHE_ALLOWED_ORIGINS` on the gateway is
// only needed when the two are deployed on different origins.
const gatewayTarget = process.env.SHE_GATEWAY_URL ?? "http://127.0.0.1:8788";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/v1": { target: gatewayTarget, changeOrigin: false },
      "/health": { target: gatewayTarget, changeOrigin: false },
    },
  },
  test: {
    include: ["tests/**/*.test.ts"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
