import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/analyze": "http://localhost:8000",
      "/generate": "http://localhost:8000",
      "/save": "http://localhost:8000",
      "/live": {
        target: "ws://localhost:8000",
        ws: true,
      },
      "/outputs": "http://localhost:8000",
    },
  },
});
