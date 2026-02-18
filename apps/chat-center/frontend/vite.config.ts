import { defineConfig, type Plugin, type ViteDevServer, type PreviewServer } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import type { IncomingMessage, ServerResponse } from 'node:http'

type NextFn = (err?: unknown) => void

const appEntryRedirectPlugin: Plugin = {
  name: 'app-entry-redirect',
  configureServer(server: ViteDevServer) {
    server.middlewares.use((req: IncomingMessage, res: ServerResponse, next: NextFn) => {
      if (req.url === '/app') {
        res.statusCode = 302
        res.setHeader('Location', '/app/')
        res.end()
        return
      }
      next()
    })
  },
  configurePreviewServer(server: PreviewServer) {
    server.middlewares.use((req: IncomingMessage, res: ServerResponse, next: NextFn) => {
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
