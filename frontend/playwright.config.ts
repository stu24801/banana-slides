import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E測試配置 - 前端 UI 測試
 * 
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // 測試目錄
  testDir: './e2e',
  
  // 測試檔案匹配模式
  testMatch: '**/*.spec.ts',
  
  // 並行執行測試
  fullyParallel: true,
  
  // CI環境下失敗立即停止
  forbidOnly: !!process.env.CI,
  
  // 失敗重試次數
  retries: process.env.CI ? 2 : 0,
  
  // 並行worker數量
  workers: process.env.CI ? 1 : undefined,
  
  // 測試報告
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
    ...(process.env.CI ? [['github'] as const] : []),
  ],
  
  // 全域性設定
  use: {
    // 基礎URL
    baseURL: 'http://localhost:3000',
    
    // 截圖設定
    screenshot: 'only-on-failure',
    
    // 影片設定
    video: 'retain-on-failure',
    
    // 追蹤設定
    trace: 'retain-on-failure',
    
    // 超時設定
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  
  // 全域性超時
  timeout: 60000,
  
  // 預期超時
  expect: {
    timeout: 10000,
  },
  
  // 專案配置（多瀏覽器測試）
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  
  // 本地開發時啟動服務
  webServer: process.env.CI ? undefined : {
    command: 'cd .. && docker compose up -d && sleep 10',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
})

