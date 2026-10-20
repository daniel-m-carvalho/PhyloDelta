import react from "@vitejs/plugin-react";
import { defaultClientConditions, defineConfig } from "vite";

/**
 * The library is read from its TypeScript source, not from its published
 * build (§48): its package.json lists a `source` condition first, which only
 * this app (and its tests and typecheck) enables. So the library needs no
 * build in development, its edits hot-reload, and the Docker image builds the
 * app from the same source.
 */
export const LIBRARY_SOURCE = "source";

/**
 * The dev server proxies /api to the backend.
 *
 * Not because CORS would block it — the API allows every origin, since its
 * credentials are bearer tokens a browser never attaches by itself — but
 * because it keeps one origin in development and in the container, so the
 * client never needs to know where the backend lives.
 */
export default defineConfig({
  plugins: [react()],
  resolve: { conditions: [LIBRARY_SOURCE, ...defaultClientConditions] },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.PHYLODELTA_API ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
