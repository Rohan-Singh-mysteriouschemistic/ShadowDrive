import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
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
        target: 'http://client:8001',
        changeOrigin: true,
      },
      '/server-api': {
        target: 'http://api:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/server-api/, '')
      }
    }
  }
})
