import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

const appEntryRedirectPlugin = {
  name: 'app-entry-redirect',
  configureServer(server: any) {
    server.middlewares.use((req: any, res: any, next: any) => {
      if (req.url === '/app') {
        res.statusCode = 302
        res.setHeader('Location', '/app/')
        res.end()
        return
      }
      next()
    })
  },
  configurePreviewServer(server: any) {
    server.middlewares.use((req: any, res: any, next: any) => {
      if (req.url === '/app') {
        res.statusCode = 302
        res.setHeader('Location', '/app/')
        res.end()
        return
      }
      next()
    })
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), appEntryRedirectPlugin],
  build: {
    rollupOptions: {
      input: {
        landing: resolve(__dirname, 'index.html'),
        app: resolve(__dirname, 'app/index.html'),
      },
    },
  },
})
