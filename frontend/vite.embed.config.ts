import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  esbuild: { charset: "ascii" },
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    emptyOutDir: false,
    lib: {
      entry: "src/embed.tsx",
      name: "SlyfBoardEmbed",
      formats: ["iife"],
      fileName: () => "embed.js",
    },
  },
});
