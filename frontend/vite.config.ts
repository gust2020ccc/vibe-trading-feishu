import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/strategies': 'http://127.0.0.1:8000',
      '/factors': 'http://127.0.0.1:8000',
      '/marketplace': 'http://127.0.0.1:8000',
      '/backtest': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/settings': 'http://127.0.0.1:8000',
      '/sessions': 'http://127.0.0.1:8000',
      '/runs': 'http://127.0.0.1:8000',
      '/live': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/skills': 'http://127.0.0.1:8000',
      '/correlation': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
