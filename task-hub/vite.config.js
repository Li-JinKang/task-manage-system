import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import viteCompression from 'vite-plugin-compression'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ command }) => ({
  // GitHub Pages 地址带仓库名，仅打包时使用子路径
  base: command === 'build' ? '/task-manage-system/' : '/',
  plugins: [
    vue(),
    tailwindcss(),
    viteCompression({
      threshold: 10240,
      algorithm: 'gzip',
      ext: '.gz',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (/node_modules\/(vue|vue-router|pinia|@vue)\//.test(id)) {
            return 'vue-vendor'
          }
        },
      },
    },
  },
}))
