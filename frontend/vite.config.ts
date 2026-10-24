import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const apiPort = process.env.RENTAL_DEV_API_PORT ?? "8000";
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [{ name: "vendor", test: /node_modules/ }],
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": `http://127.0.0.1:${apiPort}` },
  },
  preview: {
    port: 4173,
    strictPort: true,
    proxy: { "/api": `http://127.0.0.1:${apiPort}` },
  },
});
