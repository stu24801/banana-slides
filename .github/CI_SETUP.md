# CI/CD 配置說明

本專案使用GitHub Actions實現自動化CI/CD，包含**Light檢查**和**Full測試**兩個層級。

## 📋 CI架構概覽

### 🚀 Light檢查 - PR快速反饋
**觸發時機**: 提交PR時自動執行  
**耗時**: 2-5分鐘  
**工作流**: `.github/workflows/pr-quick-check.yml`

包含：
- ✅ 程式碼語法檢查（flake8, ESLint）
- ✅ 程式碼格式檢查（black, prettier）
- ✅ TypeScript構建檢查
- ✅ 後端冒煙測試（健康檢查）
- ✅ PR自動評論

### 🎯 Full測試 - 完整驗證
**觸發時機**:
1. **PR新增`ready-for-test`標籤時** 👈 推薦方式
2. 直接Push到`main`或`develop`分支（不透過PR）

**注意**：PR合併後**不會**再次執行完整測試，避免重複浪費資源

**耗時**: 15-30分鐘  
**工作流**: `.github/workflows/ci-test.yml`

包含：
- ✅ 後端單元測試（pytest + coverage）
- ✅ 後端整合測試（使用 mock AI）
- ✅ 前端測試（Vitest + coverage）
- ✅ Docker 環境測試（容器構建、啟動、健康檢查）
- ✅ **E2E 測試（從建立到匯出 PPT）**
  - 需要真實 Google Gemini API key
  - 測試完整的 AI 生成流程
  - 如果未配置 API key，會自動跳過並顯示說明
- ✅ 安全掃描（依賴漏洞檢查）

---

## 🔧 配置步驟

### 1. 配置GitHub Secrets（必需）

為了執行完整的E2E測試（包含真實AI生成），需要配置以下Secrets：

#### 步驟：
1. 進入GitHub倉庫頁面
2. 點選 `Settings` → `Secrets and variables` → `Actions`
3. 點選 `New repository secret`
4. 新增以下Secret：

| Secret名稱 | 必需 | 說明 | 獲取方式 |
|-----------|------|------|---------|
| `GOOGLE_API_KEY` | ✅ 必需 | Google Gemini API金鑰（用於完整E2E測試） | [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| `OPENAI_API_KEY` | ⚪ 可選 | OpenAI API金鑰（用於整合測試驗證相容性） | [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `SECRET_KEY` | ⚪ 可選 | Flask應用金鑰（生產環境建議配置） | 隨機生成，建議使用：`python -c "import secrets; print(secrets.token_hex(32))"` |
| `MINERU_TOKEN` | ⚪ 可選 | MinerU服務Token（如果使用MinerU解析） | 從MinerU服務獲取 |

**關於 E2E 測試策略**：
- 💡 **單一 E2E 測試**：使用 Gemini 格式測試完整流程（建立→大綱→描述→圖片→匯出）
- 💰 **成本最佳化**：只執行一次完整 E2E，避免重複測試
- ⚠️ **條件執行**：只在配置了真實 `GOOGLE_API_KEY` 時執行

**注意**：
- ⚠️ **沒有配置 `GOOGLE_API_KEY` 時，E2E 測試會被跳過**
- ✅ 其他測試（單元、整合、Docker）仍會執行，覆蓋大部分功能
- 💰 真實 API 呼叫會消耗配額（約 $0.01-0.05/次），建議使用測試專用賬號
- 🔧 CI 會自動將 Secrets 替換到 `.env` 檔案中對應的佔位符

**CI如何處理Secrets**：

CI配置會自動處理以下邏輯：

1. **複製`.env.example`到`.env`**（保持所有預設配置）
2. **自動檢測並替換Secrets**：
   - 如果GitHub Secrets中配置了某個Secret → 自動替換`.env`中對應的佔位符
   - 如果沒有配置 → 保持`.env.example`中的預設值

**支援的Secrets列表**：

CI配置會自動檢測並替換以下Secrets（如果配置了的話）：

- ✅ `GOOGLE_API_KEY` - 必需，如果沒有配置則使用`mock-api-key`
- ⚪ `OPENAI_API_KEY` - 可選，如果配置了則替換
- ⚪ `SECRET_KEY` - 可選，生產環境建議配置
- ⚪ `MINERU_TOKEN` - 可選，如果使用MinerU服務則配置

**新增新的Secret支援**：

如果需要支援其他配置項的Secret替換，只需在`.github/workflows/ci-test.yml`中新增對應的檢查邏輯：

```yaml
# 在"設定環境變數"步驟中新增
if [ -n "${{ secrets.YOUR_NEW_SECRET }}" ]; then
  sed -i '/^YOUR_ENV_VAR=/s/placeholder/${{ secrets.YOUR_NEW_SECRET }}/' .env
  echo "✓ 已替換 YOUR_ENV_VAR"
fi
```

### 2. （可選）配置CodeCov

如果需要程式碼覆蓋率報告和徽章：

1. 訪問 [codecov.io](https://codecov.io)
2. 關聯GitHub賬號並授權倉庫
3. 獲取Upload Token（通常不需要，公開倉庫自動識別）
4. 如需手動配置，新增Secret：`CODECOV_TOKEN`

---

## 🏷️ 如何觸發Full測試

### 方法1：PR新增標籤觸發（✅ 推薦）

當你認為PR已經準備好進行完整測試時：

```bash
# 在PR頁面右側，點選 "Labels"
# 新增 "ready-for-test" 標籤
```

這會立即觸發完整測試套件，包括：
- ✅ 所有單元和整合測試
- ✅ Docker 環境測試
- ✅ **E2E 測試（如果配置了真實 API key）**

**測試透過後，直接合並即可！合併後不會重複執行測試。**

**E2E 測試說明**：
- 如果配置了 `GOOGLE_API_KEY`：執行完整 E2E（額外 10-15 分鐘）
- 如果未配置：跳過 E2E，顯示友好說明（其他測試已覆蓋大部分功能）

### 方法2：手動觸發（✅ 新增）

在GitHub Actions頁面手動執行Full Test：

1. 進入倉庫頁面
2. 點選 **Actions** 標籤
3. 在左側選擇 **Full Test Suite**
4. 點選右側的 **Run workflow** 按鈕
5. 選擇分支（通常是`main`或`develop`）
6. 點選 **Run workflow**

**適用場景**：
- ✅ 想在任何時候驗證程式碼
- ✅ 除錯CI問題
- ✅ 驗證main分支的當前狀態

### 方法3：直接Push到main

如果你直接push到`main`或`develop`分支（不透過PR），會自動執行完整測試。

**注意**：
- ⚠️ **PR合並不會觸發Full測試**（避免重複）
- ✅ 請確保PR在合併前已透過`ready-for-test`測試
- 🔒 建議在倉庫設定中啟用分支保護，要求`ready-for-test`狀態透過才能合併

---

## 🔒 建議：啟用分支保護規則

為了確保所有PR在合併前都經過完整測試，建議配置GitHub分支保護：

### 配置步驟

1. 進入倉庫 → `Settings` → `Branches`
2. 在 `Branch protection rules` 下點選 `Add rule`
3. 配置如下：
   - **Branch name pattern**: `main`
   - ✅ **Require status checks to pass before merging**
     - 搜尋並勾選 `Backend Unit Tests`（或其他關鍵測試）
   - ✅ **Require branches to be up to date before merging**
   - 可選：**Require pull request reviews before merging**

### 效果

配置後，PR只有在以下條件滿足時才能合併：
- ✅ Light檢查透過（自動執行）
- ✅ Full測試透過（透過`ready-for-test`標籤觸發）
- ✅ 程式碼review透過（如果啟用）

這樣可以完全避免未測試程式碼進入`main`分支！

---

## 🧪 測試檔案說明

### Light檢查測試
- **前端Lint**: `frontend/src/**/*.{ts,tsx}`
- **後端語法**: `backend/**/*.py`
- **冒煙測試**: 啟動後端並檢查`/health`端點

### Full測試檔案
```
backend/tests/
├── unit/              # 後端單元測試
│   ├── test_ai_service.py
│   ├── test_file_service.py
│   └── ...
├── integration/       # 後端整合測試
│   ├── test_api.py
│   └── ...

frontend/src/
├── **/*.test.tsx     # 前端元件測試
└── **/*.spec.tsx     # 前端功能測試

e2e/
├── home.spec.ts           # 首頁UI測試
├── create-ppt.spec.ts     # PPT建立基礎測試
└── full-flow.spec.ts      # 🎯 完整流程測試（建立→大綱→描述→圖片→匯出）
```

---

## 📊 測試結果檢視

### CI狀態檢查
- PR頁面底部會顯示所有檢查狀態
- 點選 `Details` 檢視詳細日誌
- Light檢查會在PR評論中自動釋出結果

### 測試報告和覆蓋率
- **程式碼覆蓋率**: 自動上傳到CodeCov（如果配置）
- **E2E測試報告**: 失敗時會上傳Playwright報告和截圖
  - 在Actions頁面 → 對應的workflow run → `Artifacts` 下載
  - `playwright-report`: HTML測試報告
  - `playwright-screenshots`: 失敗時的截圖和影片

### 檢視日誌
```bash
# 本地檢視Actions日誌
gh run list
gh run view <run-id> --log
```

---

## 🚨 常見問題

### Q1: E2E測試超時失敗
**原因**: AI生成需要較長時間  
**解決**: 
- 檢查API key是否有效
- 檢查API配額是否用盡
- 本地執行測試驗證：`npx playwright test full-flow.spec.ts`

### Q2: Docker測試失敗
**原因**: 容器啟動超時或埠衝突  
**解決**:
- 檢查`docker-compose.yml`配置
- 檢視容器日誌（CI會在失敗時自動顯示）
- 本地測試：`./scripts/test_docker_environment.sh`

### Q3: 前端構建失敗
**原因**: TypeScript型別錯誤或依賴問題  
**解決**:
- 本地執行：`cd frontend && npm run build:check`
- 檢查`frontend/package.json`依賴版本
- 確保`package-lock.json`已提交

### Q4: "ready-for-test"標籤不觸發測試
**原因**: Workflow許可權或配置問題  
**解決**:
- 確認標籤名稱完全匹配（小寫，帶連字元）
- 檢查倉庫Settings → Actions → General → Workflow permissions
- 檢視Actions頁面確認workflow是否被觸發

---

## 📝 本地測試

### 🚀 快速開始

```bash
# Light檢查（2-3分鐘）- 提交前快速檢查
./scripts/run-local-ci.sh light

# Full測試（10-20分鐘）- PR合併前完整測試
./scripts/run-local-ci.sh full
```

### 🔧 前置依賴

```bash
# Python環境 (>= 3.10)
python3 --version

# Node.js環境 (>= 18)
node --version

# UV包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# Docker
docker --version
docker compose --version

# 安裝依賴
uv sync --extra test
cd frontend && npm ci
npx playwright install --with-deps chromium
```

### 🧪 執行特定測試

```bash
# 後端單元測試
cd backend
uv run pytest tests/unit -v --cov=. --cov-report=html

# 前端測試
cd frontend
npm test -- --coverage

# E2E測試（需要真實API key）
cp .env.example .env  # 編輯.env填入真實API金鑰
docker compose up -d
npx playwright test full-flow.spec.ts

# Docker環境測試
./scripts/test_docker_environment.sh
```

### 🐛 除錯失敗的測試

```bash
# E2E UI模式除錯
npx playwright test --ui

# 後端除錯模式
cd backend
uv run pytest tests/unit/test_xxx.py --pdb

# 檢視Docker日誌
docker compose logs backend
docker compose logs frontend
```

---

## 🎯 最佳實踐

### 開發流程建議

1. **開發階段**：
   - 頻繁提交小改動
   - 依賴Light檢查快速反饋
   - 修復lint和構建錯誤

2. **功能完成後**：
   - 自測主要功能
   - 執行本地測試套件
   - 提交PR

3. **準備合併前**：
   - 新增`ready-for-test`標籤 👈 **關鍵步驟**
   - 等待Full測試透過
   - Code review透過後合併
   - 合併後**不會重複執行測試**，節省資源 ✅

4. **合併後**：
   - 程式碼直接進入`main`分支
   - 無需等待額外的CI執行
   - 節省時間和成本

### CI最佳化建議

- ✅ 保持測試快速（單元測試 < 5分鐘）
- ✅ E2E測試只驗證關鍵流程
- ✅ 使用快取加速依賴安裝
- ✅ 並行執行獨立測試
- ✅ 失敗快速反饋（fail-fast）

---

## 📚 相關文件

- [GitHub Actions文件](https://docs.github.com/en/actions)
- [Playwright測試文件](https://playwright.dev)
- [pytest文件](https://docs.pytest.org)
- [Vitest文件](https://vitest.dev)

---

## 🆘 需要幫助？

如果遇到CI問題：
1. 檢視Actions日誌詳細錯誤資訊
2. 參考本文件常見問題部分
3. 在issue中提問並附上錯誤日誌
4. 聯絡維護者

---

**最後更新**: 2025-01-20  
**維護者**: Banana Slides Team

