import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// In Docker the API is reachable as http://api:8000; outside Docker it's on localhost.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/api': { target: apiUrl, rewrite: (path) => path.replace(/^\/api/, '') } },
  },
});
