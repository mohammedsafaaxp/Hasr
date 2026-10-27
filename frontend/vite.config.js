import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: '/hasr',
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      codeLanguages: false,
      buildConfig: { indexHtmlPath: '../hasr/www/hasr.html', emptyOutDir: true },
    }),
    vue(),
  ],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
    dedupe: ['vue', 'vue-router', 'frappe-ui'],
  },
  optimizeDeps: { include: ['tailwind.config.js'], exclude: ['frappe-ui'] },
})
