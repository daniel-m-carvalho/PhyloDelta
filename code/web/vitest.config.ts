import { defaultClientConditions } from "vite";
import { defineConfig } from "vitest/config";

import { LIBRARY_SOURCE } from "./vite.config";

export default defineConfig({
  // The library's source rather than its build, as in vite.config.ts.
  resolve: { conditions: [LIBRARY_SOURCE, ...defaultClientConditions] },
  test: {
    // jsdom for the hooks that touch window.location and the DOM; the pure
    // modules do not care either way.
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    globals: false,
  },
});
