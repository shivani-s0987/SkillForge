import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  // 👇 Use /SkillForge/ for GitHub Pages, but automatically use / in local dev
  base: process.env.NODE_ENV === 'production' ? '/SkillForge/' : '/',
  server: {
    port: 9000,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
})
