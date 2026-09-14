import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // The backend port for the dev proxy. Prefer VITE_API_URL, then BACKEND_PORT,
  // then the FastAPI default. Note: VITE_* vars are only auto-exposed to the
  // client bundle when set in .env files, so also honor BACKEND_PORT which
  // works regardless of how the dev server is launched.
  const backendPort = env.BACKEND_PORT || (env.VITE_API_URL ? new URL(env.VITE_API_URL).port : "") || "8000";
  const proxyTarget = env.VITE_API_URL?.startsWith("http")
    ? env.VITE_API_URL
    : `http://localhost:${backendPort}`;
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/tests/setup.ts",
      css: false,
    },
  };
});
