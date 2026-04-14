import { defineConfig } from "vite";
import path from "path";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "src/renderer",
  base: "./",

  plugins: [react()],

  server: {
    port: 3480,
    open: false,
  },

  build: {
    outDir: "../../dist/renderer",
    emptyOutDir: true,
  },

  assetsInclude: ["**/*.svg", "**/*.csv"],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
