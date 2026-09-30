import { defineConfig } from 'vite'
import basicSsl from '@vitejs/plugin-basic-ssl'
import react from '@vitejs/plugin-react'

// Mode-based config: --mode demo and --mode phone.
export default defineConfig(({ mode, command }) => ({
  // --mode phone adds HTTPS (self-signed), which phone cameras require.
  plugins: [react(), ...(mode === 'phone' ? [basicSsl()] : [])],

  // Demo builds inject VITE_DEMO=true at build time.
  ...(mode === 'demo'
    ? {
        define: { 'import.meta.env.VITE_DEMO': JSON.stringify('true') },
        base: './',
        build: { outDir: 'dist-demo' },
      }
    : command === 'build'
      ? {
          // Real builds pin VITE_DEMO=false so the demo data is tree-shaken out.
          define: { 'import.meta.env.VITE_DEMO': JSON.stringify('false') },
        }
      : {}),

  server: {
    // Listen on all interfaces so a phone can reach the dev server.
    host: true,
    port: 5173,

    // Dev proxy: /api goes to uvicorn on :8000, so no CORS in development.
    proxy: {
      '/api': {
        target: process.env.BAR_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
}))
