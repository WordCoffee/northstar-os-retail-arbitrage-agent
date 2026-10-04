import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/',  // canonical frontend is served under /ui/ by FastAPI
  plugins: [react()],
  build: {
    // Split vendor code so the app chunk stays well under the 500 kB warning
    // threshold. Pure build-config change; no runtime behavior change.
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
  server: {
    port: 8101,
    strictPort: true,
    host: '0.0.0.0',
    proxy: {
      // All backend calls route to the FastAPI service on :8000
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/autothink': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/legal': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  preview: {
    port: 8101,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/autothink': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/legal': { target: 'http://127.0.0.1:8000', changeOrigin: true }
    }
  }
})