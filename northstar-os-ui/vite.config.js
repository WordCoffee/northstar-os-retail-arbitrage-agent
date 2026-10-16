import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'node:child_process'

// Build banner (2026-10-16): the shell shows the commit + build time so a
// stale image can never be mistaken for the current tree again.
function buildInfo() {
  let commit = 'unknown'
  let time = new Date().toISOString()
  try {
    commit = execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim()
    time = execSync('git log -1 --format=%cI', { encoding: 'utf8' }).trim() || time
  } catch { /* not a git checkout at build time */ }
  return { commit, time }
}

export default defineConfig({
  base: '/ui/',  // canonical frontend is served under /ui/ by FastAPI
  plugins: [react()],
  define: {
    __BUILD_INFO__: JSON.stringify(buildInfo()),
  },
  build: {
    // Split vendor code so the app chunk stays well under the 500 kB warning
    // threshold. Pure build-config change; no runtime behavior change.
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          // The creative studio engine (document model, 3D renderer, mockups,
          // asset store, presets) is only needed by the two creative rooms.
          studio: [
            './src/studio/engine/doc.js',
            './src/studio/engine/presets.js',
            './src/studio/engine/three.js',
            './src/studio/engine/mockups.js',
            './src/studio/engine/sceneDoc.js',
            './src/studio/engine/assets.js',
          ],
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