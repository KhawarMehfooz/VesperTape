import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Preserve the browser-facing Host so API same-origin checks work.
      '/api': { target: 'http://localhost:8000', changeOrigin: false },
    },
  },
})
