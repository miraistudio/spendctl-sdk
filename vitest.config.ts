import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const src = (path: string) => fileURLToPath(new URL(path, import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@spendctl/client": src("./packages/client/src/index.ts"),
    },
  },
  test: {
    include: ["packages/**/test/**/*.test.ts"],
    testTimeout: 20_000,
  },
});
