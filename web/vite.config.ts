import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// In Docker the API is reachable as http://api:8000; outside Docker it's on localhost.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Windows → Docker bind mounts don't deliver file-change events, so poll.
    // 1 s interval and skipping build/test output keeps polling from eating a CPU core.
    watch: {
      usePolling: true,
      interval: 1000,
      ignored: ['**/dist/**', '**/e2e/**', '**/playwright-report/**', '**/test-results/**'],
    },
    proxy: { '/api': { target: apiUrl, rewrite: (path) => path.replace(/^\/api/, '') } },
  },
});
