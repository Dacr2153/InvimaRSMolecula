import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // En desarrollo el API vive aparte; en produccion nginx hace el proxy de /api.
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY ?? 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
});
