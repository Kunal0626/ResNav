import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@styles': fileURLToPath(new URL('./styles', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // Proxy in development so the browser talks to one origin and CORS never
    // enters the picture locally. Production uses VITE_API_BASE_URL instead.
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_PROXY || 'http://127.0.0.1:5001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    // Charting and mapping libraries are large and only needed on some routes;
    // splitting them keeps the initial payload small.
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['chart.js'],
          maps: ['leaflet'],
        },
      },
    },
  },
});
