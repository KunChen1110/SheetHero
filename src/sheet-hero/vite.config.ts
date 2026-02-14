import { defineConfig } from "vite";
import path from "path";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "src/renderer",

  plugins: [react()],

  server: {
    port: 3480,
    open: false,
  },

  assetsInclude: ["**/*.svg", "**/*.csv"],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
