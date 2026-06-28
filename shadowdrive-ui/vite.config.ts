import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const isDocker = process.env.DOCKER_ENV === 'true';
const clientTarget = isDocker ? 'http://client:8001' : 'http://localhost:8001';
const apiTarget = isDocker ? 'http://api:8000' : 'http://localhost:8000';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    allowedHosts: [
      'baadal.tailb4fef9.ts.net'
    ],
    proxy: {
      '/api': {
        target: clientTarget,
        changeOrigin: true,
      },
      '/server-api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/server-api/, '')
      }
    }
  }
})
