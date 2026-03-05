# 蕉幻 (Banana Slides) 前端

這是蕉幻 AI PPT 生成器的前端應用。

## 技術棧

- **框架**: React 18 + TypeScript
- **構建工具**: Vite
- **狀態管理**: Zustand
- **樣式**: TailwindCSS
- **路由**: React Router
- **拖拽**: @dnd-kit
- **圖示**: Lucide React

## 開始開發

### 1. 安裝依賴

```bash
npm install
```

### 2. 配置環境變數

**注意**：現在不再需要配置 `VITE_API_BASE_URL`！

前端使用相對路徑，透過代理自動轉發到後端：
- **開發環境**：透過 Vite proxy 自動轉發到後端
- **生產環境**：透過 nginx proxy 自動轉發到後端服務

**一鍵修改後端埠**：
只需在專案根目錄的 `.env` 檔案中修改 `BACKEND_PORT` 環境變數（預設 5000），前端和後端都會自動使用新埠：

```env
BACKEND_PORT=8080  # 修改為 8080 或其他埠
```

這樣無論後端執行在什麼地址（localhost、IP 或域名），前端都能自動適配，無需手動配置。

### 3. 啟動開發伺服器

```bash
npm run dev
```

應用將在 http://localhost:3000 啟動

### 4. 構建生產版本

```bash
npm run build
```

## 專案結構

```
src/
├── api/              # API 封裝
│   ├── client.ts     # Axios 例項配置
│   └── endpoints.ts  # API 端點
├── components/       # 元件
│   ├── shared/       # 通用元件
│   ├── outline/      # 大綱編輯元件
│   └── preview/      # 預覽元件
├── pages/            # 頁面
│   ├── Home.tsx      # 首頁
│   ├── OutlineEditor.tsx    # 大綱編輯頁
│   ├── DetailEditor.tsx     # 詳細描述編輯頁
│   └── SlidePreview.tsx     # 預覽頁
├── store/            # 狀態管理
│   └── useProjectStore.ts
├── types/            # TypeScript 型別
│   └── index.ts
├── utils/            # 工具函式
│   └── index.ts
├── App.tsx           # 應用入口
├── main.tsx          # React 掛載點
└── index.css         # 全域性樣式
```

## 主要功能

### 1. 首頁 (/)
- 三種建立方式：一句話生成、從大綱生成、從描述生成
- 風格模板選擇和上傳

### 2. 大綱編輯頁 (/project/:id/outline)
- 拖拽排序頁面
- 編輯大綱內容
- 自動生成大綱

### 3. 詳細描述編輯頁 (/project/:id/detail)
- 批次生成頁面描述
- 編輯單頁描述
- 網格展示所有頁面

### 4. 預覽頁 (/project/:id/preview)
- 檢視生成的圖片
- 編輯單頁（自然語言修改）
- 匯出為 PPTX/PDF

## 開發注意事項

### 狀態管理
- 使用 Zustand 進行全域性狀態管理
- 關鍵狀態會同步到 localStorage
- 頁面重新整理後自動恢復專案

### 非同步任務
- 使用輪詢機制監控長時間任務
- 顯示實時進度
- 完成後自動重新整理資料

### 圖片處理
- 所有圖片路徑需透過 `getImageUrl()` 處理
- 支援相對路徑和絕對路徑

### 拖拽功能
- 使用 @dnd-kit 實現
- 支援鍵盤操作
- 樂觀更新 UI

## 與後端整合

確保後端服務執行在配置的埠（預設 5000）：

```bash
cd ../backend
python app.py
```

## 瀏覽器支援

- Chrome (推薦)
- Firefox
- Safari
- Edge

