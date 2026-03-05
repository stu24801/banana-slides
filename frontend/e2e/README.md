# E2E 測試說明

## 📋 測試策略

本專案採用**單一真正的 E2E 測試**策略，避免"偽 E2E"測試造成混淆。

### 測試金字塔

```
        ┌──────────────────┐
        │   E2E 測試        │  ← 少量，測試完整流程，需要真實 API
        │  (api-full-flow)  │
        └──────────────────┘
              ▲
              │
      ┌───────────────────┐
      │   整合測試         │  ← 中等，測試 API 端點，使用 mock
      │  (backend/tests/)  │
      └───────────────────┘
            ▲
            │
    ┌─────────────────────┐
    │   單元測試           │  ← 大量，快速，獨立
    │ (前端 + 後端)        │
    └─────────────────────┘
```

---

## 🎯 E2E 測試檔案

### 1. **api-full-flow.spec.ts** ⭐ 主要 E2E 測試

**特點**：
- ✅ 真正的端到端測試（完整流程）
- ✅ 使用真實的 AI API（Google Gemini）
- ✅ 測試從建立到匯出的完整鏈路
- ✅ 在 CI 中自動執行（如果配置了 API key）

**測試流程**：
```
1. 建立專案（從想法/大綱/描述）
   ↓
2. 等待 AI 生成大綱
   ↓
3. 生成頁面描述
   ↓
4. 生成頁面圖片
   ↓
5. 匯出 PPT 檔案
```

**執行條件**：
- ⚠️ 需要真實的 `GOOGLE_API_KEY`
- ⚠️ 需要約 10-15 分鐘
- ⚠️ 會消耗 API 配額（約 $0.01-0.05/次）

**本地執行**：
```bash
# 1. 確保 .env 中配置了真實的 GOOGLE_API_KEY
# 2. 啟動服務
docker compose up -d

# 3. 等待服務就緒（使用智慧等待指令碼）
./scripts/wait-for-health.sh http://localhost:5000/health 60 2
./scripts/wait-for-health.sh http://localhost:3000 60 2

# 4. 執行測試
npx playwright test api-full-flow.spec.ts --workers=1
```

**CI 執行**：
- 自動執行：在 `docker-test` job 中
- 條件：`GOOGLE_API_KEY` 已在 GitHub Secrets 中配置
- 跳過：如果沒有配置 API key，會跳過並顯示說明

---

### 2. **ui-full-flow.spec.ts** 🎨 UI 驅動的完整測試

**特點**：
- ✅ 從瀏覽器 UI 開始操作（模擬真實使用者）
- ✅ 測試完整的使用者互動流程
- ✅ 需要真實的 AI API（Google Gemini）
- ⚠️ 執行時間更長（15-20 分鐘）
- ✅ 在 CI 中自動執行（如果有 API key）

**用途**：
- 釋出前的最終驗證
- 驗證真實使用者體驗
- CI/CD 完整流程測試

**本地執行**：
```bash
# 1. 確保 .env 中配置了真實的 GOOGLE_API_KEY
# 2. 啟動服務
docker compose up -d

# 3. 等待服務就緒
./scripts/wait-for-health.sh http://localhost:5000/health 60 2
./scripts/wait-for-health.sh http://localhost:3000 60 2

# 4. 執行測試
npx playwright test ui-full-flow.spec.ts --workers=1
```

**CI 執行**：
- 自動執行：在 `docker-test` job 中
- 條件：`GOOGLE_API_KEY` 已在 GitHub Secrets 中配置
- 跳過：如果沒有配置 API key 或是 Fork PR，會跳過並顯示說明

---

## 🚫 已刪除的測試

以下測試檔案已被刪除（避免混淆）：

- ~~`home.spec.ts`~~ - 基礎 UI 測試（不是真正的 E2E）
- ~~`create-ppt.spec.ts`~~ - API 整合測試（不是真正的 E2E）

**原因**：
- 它們不呼叫真實 AI API，不是真正的端到端測試
- 測試的內容已被其他測試覆蓋：
  - UI 互動 → 前端單元測試
  - API 端點 → 後端整合測試
  - 完整流程 → `api-full-flow.spec.ts`

---

## 🔧 CI 配置

### 在 GitHub Actions 中的執行邏輯

```yaml
# .github/workflows/ci-test.yml

docker-test job:
  ├─ 構建 Docker 映象
  ├─ 啟動服務
  ├─ 健康檢查
  ├─ Docker 環境測試
  └─ E2E 測試 (api-full-flow.spec.ts)
      ├─ 如果有 GOOGLE_API_KEY → 執行完整 E2E
      └─ 如果沒有 API key → 跳過，顯示說明
```

### 配置 GitHub Secrets

要在 CI 中執行 E2E 測試，需要配置：

1. 進入倉庫 → **Settings** → **Secrets and variables** → **Actions**
2. 新增 Secret：
   - Name: `GOOGLE_API_KEY`
   - Value: 你的 Google Gemini API 金鑰
   - 獲取地址：https://aistudio.google.com/app/apikey

### 如果沒有配置 API key

CI 會跳過 E2E 測試，並顯示：

```
⚠️  Skipping E2E tests

Reason: GOOGLE_API_KEY not configured or using mock key

Note: Other tests already passed:
  ✅ Backend unit tests
  ✅ Backend integration tests (with mock AI)
  ✅ Frontend unit tests
  ✅ Docker environment tests

E2E tests require a real Google API key to test the complete AI generation workflow.
```

**這是正常的！** 其他測試已經覆蓋了大部分功能。

---

## 📊 測試覆蓋範圍

| 測試層級 | 測試內容 | 需要真實 API | 執行時間 | CI 執行 |
|---------|---------|-------------|---------|---------|
| **前端單元測試** | React 元件、hooks、工具函式 | ❌ | < 1 分鐘 | ✅ 總是 |
| **後端單元測試** | Services、Utils、Models | ❌ | < 2 分鐘 | ✅ 總是 |
| **後端整合測試** | API 端點（mock AI） | ❌ | < 3 分鐘 | ✅ 總是 |
| **Docker 環境測試** | 容器啟動、健康檢查 | ❌ | < 5 分鐘 | ✅ 總是 |
| **E2E 測試** | 完整 AI 生成流程 | ✅ | 10-15 分鐘 | ⚠️ 有 API key 時 |

---

## 🎯 最佳實踐

### 開發時

1. **日常開發**：執行單元測試和整合測試
   ```bash
   # 後端
   cd backend && uv run pytest tests/
   
   # 前端
   cd frontend && npm test
   ```

2. **提交 PR 前**：確保 CI 的所有測試透過
   - Light Check（自動執行）
   - Full Test（新增 `ready-for-test` 標籤觸發）

3. **大功能完成後**：本地執行一次 E2E 測試
   ```bash
   # 確保 .env 配置了真實 API key
   npx playwright test api-full-flow.spec.ts
   ```

### 釋出前

1. **最終驗證**：執行完整的 UI E2E 測試
   ```bash
   npx playwright test ui-full-flow.spec.ts
   ```

2. **檢查 CI**：確保所有測試（包括 E2E）都透過

---

## 🐛 除錯失敗的測試

### 檢視測試報告

```bash
# 執行測試後，開啟 HTML 報告
npx playwright show-report
```

### 檢視失敗截圖和影片

測試失敗時，Playwright 會自動儲存：
- 截圖：`test-results/**/test-failed-*.png`
- 影片：`test-results/**/video.webm`
- 追蹤：`test-results/**/trace.zip`

### 檢視追蹤

```bash
npx playwright show-trace test-results/**/trace.zip
```

### UI 模式除錯

```bash
# 在 UI 模式下執行測試（可以看到瀏覽器操作過程）
npx playwright test --ui
```

---

## 📚 相關文件

- [Playwright 文件](https://playwright.dev)
- [CI 配置說明](../.github/CI_SETUP.md)
- [專案 README](../README.md)

---

**最後更新**: 2025-12-22  
**測試策略**: 單一真正的 E2E 測試
