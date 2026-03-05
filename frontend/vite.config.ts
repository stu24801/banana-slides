/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 從專案根目錄讀取 .env 檔案（相對於 frontend 目錄的上一級）
  const envDir = path.resolve(__dirname, '..')
  
  // 使用 loadEnv 載入環境變數（第三個引數為空字串表示載入所有變數，不僅僅是 VITE_ 字首的）
  const env = loadEnv(mode, envDir, '')
  
  // 讀取後端埠，預設 5000
  const backendPort = env.BACKEND_PORT || '5000'
  const backendUrl = `http://localhost:${backendPort}`
  
  return {
    base: '/slides/',
    envDir,
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      host: true, // 監聽所有地址
      watch: {
        usePolling: true, // WSL 環境下需要啟用輪詢
      },
      hmr: {
        overlay: true, // 顯示錯誤覆蓋層
      },
      proxy: {
        // API 請求代理到後端（埠從環境變數 BACKEND_PORT 讀取）
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
        // 檔案服務代理到後端
        '/files': {
          target: backendUrl,
          changeOrigin: true,
        },
        // 健康檢查代理到後端
        '/health': {
          target: backendUrl,
          changeOrigin: true,
        },
      },
    },
    // Vitest 測試配置
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/tests/setup.ts',
      include: ['src/**/*.{test,spec}.{js,ts,jsx,tsx}'],
      exclude: ['node_modules', 'dist'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
        exclude: [
          'node_modules/',
          'src/tests/',
          '**/*.d.ts',
          '**/*.config.*',
        ],
      },
    },
  }
})
