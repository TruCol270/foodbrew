import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // The dev server proxies the API so the browser sees one origin, which is
    // why the backend ships no CORS middleware (plan decision #11).
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: { outDir: 'dist' },
})
