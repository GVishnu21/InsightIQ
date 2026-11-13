import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom', // a fake browser, so React components can be rendered in tests
    setupFiles: ['./src/test/setup.js'],
    css: false,
  },
})
