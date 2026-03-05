<div align="center">

<img width="256" src="https://github.com/user-attachments/assets/6f9e4cf9-912d-4faa-9d37-54fb676f547e">

*Vibe your PPT like vibing code.*

**中文 | [English](README_EN.md)**

<p>

[![GitHub Stars](https://img.shields.io/github/stars/Anionex/banana-slides?style=square)](https://github.com/Anionex/banana-slides/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/Anionex/banana-slides?style=square)](https://github.com/Anionex/banana-slides/network)
[![GitHub Watchers](https://img.shields.io/github/watchers/Anionex/banana-slides?style=square)](https://github.com/Anionex/banana-slides/watchers)

[![Version](https://img.shields.io/badge/version-v0.3.0-4CAF50.svg)](https://github.com/Anionex/banana-slides)
![Docker](https://img.shields.io/badge/Docker-Build-2496ED?logo=docker&logoColor=white)
[![GitHub issues](https://img.shields.io/github/issues-raw/Anionex/banana-slides)](https://github.com/Anionex/banana-slides/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr-raw/Anionex/banana-slides)](https://github.com/Anionex/banana-slides/pulls)


</p> 

<b>一個基於nano banana pro🍌的原生AI PPT生成應用，支援想法/大綱/頁面描述生成完整PPT簡報，<br></b>
<b> 自動提取附件圖表、上傳任意素材、口頭提出修改，邁向真正的"Vibe PPT" </b>

<b>🎯 降低PPT製作門檻，讓每個人都能快速創作出美觀專業的簡報</b>

<br>

*如果該專案對你有用, 歡迎star🌟 &  fork🍴*

<br>

</p>

</div>



## ✨ 專案緣起
你是否也曾陷入這樣的困境：明天就要彙報，但PPT還是一片空白；腦中有無數精彩的想法，卻被繁瑣的排版和設計消磨掉所有熱情？

我(們)渴望能快速創作出既專業又具設計感的簡報，傳統的AI PPT生成app，雖然大體滿足“快”這一需求，卻還存在以下問題：

- 1️⃣只能選擇預設模版，無法靈活調整風格
- 2️⃣自由度低，多輪改動難以進行 
- 3️⃣成品觀感相似，同質化嚴重
- 4️⃣素材質量較低，缺乏針對性
- 5️⃣圖文排版割裂，設計感差

以上這些缺陷，讓傳統的AI ppt生成器難以同時滿足我們“快”和“美”的兩大PPT製作需求。即使自稱Vibe PPT，但是在我的眼中還遠不夠“Vibe”。

但是，nano banana🍌模型的出現讓一切有了轉機。我嘗試使用🍌pro進行ppt頁面生成，發現生成的結果無論是質量、美感還是一致性，都做的非常好，且幾乎能精確渲染prompt要求的所有文字+遵循參考圖的風格。那為什麼不基於🍌pro，做一個原生的"Vibe PPT"應用呢？

## 👨‍💻 適用場景

1. **小白**：零門檻快速生成美觀PPT，無需設計經驗，減少模板選擇煩惱
2. **PPT專業人士**：參考AI生成的佈局和圖文元素組合，快速獲取設計靈感
3. **教育工作者**：將教學內容快速轉換為配圖教案PPT，提升課堂效果
4. **學生**：快速完成作業Pre，把精力專注於內容而非排版美化
5. **職場人士**：商業提案、產品介紹快速視覺化，多場景快速適配


## 🎨 結果案例


<div align="center">

| | |
|:---:|:---:|
| <img src="https://github.com/user-attachments/assets/d58ce3f7-bcec-451d-a3b9-ca3c16223644" width="500" alt="案例3"> | <img src="https://github.com/user-attachments/assets/c64cd952-2cdf-4a92-8c34-0322cbf3de4e" width="500" alt="案例2"> |
| **軟體開發最佳實踐** | **DeepSeek-V3.2技術展示** |
| <img src="https://github.com/user-attachments/assets/383eb011-a167-4343-99eb-e1d0568830c7" width="500" alt="案例4"> | <img src="https://github.com/user-attachments/assets/1a63afc9-ad05-4755-8480-fc4aa64987f1" width="500" alt="案例1"> |
| **預製菜智慧產線裝備研發和產業化** | **錢的演變：從貝殼到紙幣的旅程** |

</div>

更多可見<a href="https://github.com/Anionex/banana-slides/issues/2" > 使用案例 </a>


## 🎯 功能介紹

### 1. 靈活多樣的創作路徑
支援**想法**、**大綱**、**頁面描述**三種起步方式，滿足不同創作習慣。
- **一句話生成**：輸入一個主題，AI 自動生成結構清晰的大綱和逐頁內容描述。
- **自然語言編輯**：支援以 Vibe 形式口頭修改大綱或描述（如"把第三頁改成案例分析"），AI 實時響應調整。
- **大綱/描述模式**：既可一鍵批次生成，也可手動調整細節。

<img width="2000" height="1125" alt="image" src="https://github.com/user-attachments/assets/7fc1ecc6-433d-4157-b4ca-95fcebac66ba" />


### 2. 強大的素材解析能力
- **多格式支援**：上傳 PDF/Docx/MD/Txt 等檔案，後臺自動解析內容。
- **智慧提取**：自動識別文字中的關鍵點、圖片連結和圖表資訊，為生成提供豐富素材。
- **風格參考**：支援上傳參考圖片或模板，定製 PPT 風格。

<img width="1920" height="1080" alt="檔案解析與素材處理" src="https://github.com/user-attachments/assets/8cda1fd2-2369-4028-b310-ea6604183936" />

### 3. "Vibe" 式自然語言修改
不再受限於複雜的選單按鈕，直接透過**自然語言**下達修改指令。
- **區域性重繪**：對不滿意的區域進行口頭式修改（如"把這個圖換成餅圖"）。
- **整頁最佳化**：基於 nano banana pro🍌 生成高畫質、風格統一的頁面。

<img width="2000" height="1125" alt="image" src="https://github.com/user-attachments/assets/929ba24a-996c-4f6d-9ec6-818be6b08ea3" />


### 4. 開箱即用的格式匯出
- **多格式支援**：一鍵匯出標準 **PPTX** 或 **PDF** 檔案。
- **完美適配**：預設 16:9 比例，排版無需二次調整，直接演示。

<img width="1000" alt="image" src="https://github.com/user-attachments/assets/3e54bbba-88be-4f69-90a1-02e875c25420" />
<img width="1748" height="538" alt="PPT與PDF匯出" src="https://github.com/user-attachments/assets/647eb9b1-d0b6-42cb-a898-378ebe06c984" />

### 5. 可自由編輯的pptx匯出（Beta迭代中）
- **匯出影象為高還原度、背景乾淨的、可自由編輯影象和文字的PPT頁面**
- 相關更新見 https://github.com/Anionex/banana-slides/issues/121
<img width="1000"  alt="image" src="https://github.com/user-attachments/assets/a85d2d48-1966-4800-a4bf-73d17f914062" />

<br>

**🌟和notebooklm slide deck功能對比**
| 功能 | notebooklm | 本專案 | 
| --- | --- | --- |
| 頁數上限 | 15頁 | **無限制** | 
| 二次編輯 | 不支援 | **框選編輯+口頭編輯** |
| 素材新增 | 生成後無法新增 | **生成後自由新增** |
| 匯出格式 | 僅支援匯出為 PDF | **匯出為PDF、(可編輯)pptx** |
| 水印 | 免費版有水印 | **無水印，自由增刪元素** |

> 注：隨著新功能新增,對比可能過時



## 🔥 近期更新
- 【1-4】 : v0.3.0釋出：可編輯pptx匯出全面升級：
  * 支援最大程度還原圖片中文字的字號、顏色、加粗等樣式；
  * 支援了識別表格中的文字內容；
  * 更精確的文字大小和文字位置還原邏輯
  * 最佳化匯出工作流，大大減少了匯出後背景圖殘留文字的現象；
  * 支援頁面多選邏輯，靈活選擇需要生成和匯出的具體頁面。
  * **詳細效果和使用方法見 https://github.com/Anionex/banana-slides/issues/121**

- 【12-27】: 加入了對無圖片模板模式的支援和較高質量的文字預設，現在可以透過純文字描述的方式來控制ppt頁面風格
- 【12-24】: main分支加入了基於nano-banana-pro背景提取的可編輯pptx匯出方法（目前Beta）


## 🗺️ 開發計劃

| 狀態 | 里程碑 |
| --- | --- |
| ✅ 已完成 | 從想法、大綱、頁面描述三種路徑建立 PPT |
| ✅ 已完成 | 解析文字中的 Markdown 格式圖片 |
| ✅ 已完成 | PPT 單頁新增更多素材 |
| ✅ 已完成 | PPT 單頁框選區域Vibe口頭編輯 |
| ✅ 已完成 | 素材模組: 素材生成、上傳等 |
| ✅ 已完成 | 支援多種檔案的上傳+解析 |
| ✅ 已完成 | 支援Vibe口頭調整大綱和描述 |
| ✅ 已完成 | 初步支援可編輯版本pptx檔案匯出 |
| 🔄 進行中 | 支援多層次、精確摳圖的可編輯pptx匯出 |
| 🔄 進行中 | 網路搜尋 |
| 🔄 進行中 | Agent 模式 |
| 🧭 規劃中 | 最佳化前端載入速度 |
| 🧭 規劃中 | 線上播放功能 |
| 🧭 規劃中 | 簡單的動畫和頁面切換效果 |
| 🧭 規劃中 | 多語種支援 |
| 🧭 規劃中 | 使用者系統 |

## 📦 使用方法

### 使用 Docker Compose🐳（推薦）
這是最簡單的部署方式，可以一鍵啟動前後端服務。

<details>
  <summary>📒Windows使用者說明</summary>

如果你使用 Windows, 請先安裝 Windows Docker Desktop，檢查系統托盤中的 Docker 圖示，確保 Docker 正在執行，然後使用相同的步驟操作。

> **提示**：如果遇到問題，確保在 Docker Desktop 設定中啟用了 WSL 2 後端（推薦），並確保埠 3000 和 5000 未被佔用。

</details>

0. **克隆程式碼倉庫**
```bash
git clone https://github.com/Anionex/banana-slides
cd banana-slides
```

1. **配置環境變數**

建立 `.env` 檔案（參考 `.env.example`）：
```bash
cp .env.example .env
```

編輯 `.env` 檔案，配置必要的環境變數：
> **專案中大模型介面以AIHubMix平臺格式為標準，推薦使用 [AIHubMix](https://aihubmix.com/?aff=17EC) 獲取API金鑰，減小遷移成本**  
```env
# AI Provider格式配置 (gemini / openai / vertex)
AI_PROVIDER_FORMAT=gemini

# Gemini 格式配置（當 AI_PROVIDER_FORMAT=gemini 時使用）
GOOGLE_API_KEY=your-api-key-here
GOOGLE_API_BASE=https://generativelanguage.googleapis.com
# 代理示例: https://aihubmix.com/gemini

# OpenAI 格式配置（當 AI_PROVIDER_FORMAT=openai 時使用）
OPENAI_API_KEY=your-api-key-here
OPENAI_API_BASE=https://api.openai.com/v1
# 代理示例: https://aihubmix.com/v1

# Vertex AI 格式配置（當 AI_PROVIDER_FORMAT=vertex 時使用）
# 需要 GCP 服務賬戶，可使用 GCP 免費額度
# VERTEX_PROJECT_ID=your-gcp-project-id
# VERTEX_LOCATION=global
# GOOGLE_APPLICATION_CREDENTIALS=./gcp-service-account.json
...
```

**使用新版可編輯匯出配置方法，獲得更好的可編輯匯出效果**: 需在[百度智慧雲平臺](https://console.bce.baidu.com/iam/#/iam/apikey/list)中獲取API KEY，填寫在.env檔案中的BAIDU_OCR_API_KEY欄位（有充足的免費使用額度）。詳見https://github.com/Anionex/banana-slides/issues/121 中的說明


<details>
  <summary>📒 使用 Vertex AI（GCP 免費額度）</summary>

如果你想使用 Google Cloud Vertex AI（可使用 GCP 新使用者贈金），需要額外配置：

1. 在 [GCP Console](https://console.cloud.google.com/) 建立服務賬戶並下載 JSON 金鑰檔案
2. 將金鑰檔案重新命名為 `gcp-service-account.json` 放在專案根目錄
3. 編輯 `.env` 檔案：
   ```env
   AI_PROVIDER_FORMAT=vertex
   VERTEX_PROJECT_ID=your-gcp-project-id
   VERTEX_LOCATION=global
   ```
4. 編輯 `docker-compose.yml`，取消以下注釋：
   ```yaml
   # environment:
   #   - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-service-account.json
   # ...
   # - ./gcp-service-account.json:/app/gcp-service-account.json:ro
   ```

> **注意**：`gemini-3-*` 系列模型需要設定 `VERTEX_LOCATION=global`

</details>

2. **啟動服務**

**⚡ 使用預構建映象**

專案在 Docker Hub 提供了構建好的前端和後端映象（同步主分支最新版本），可以跳過本地構建步驟，實現快速部署：

```bash
# 使用預構建映象啟動（無需從頭構建）
docker compose -f docker-compose.prod.yml up -d
```

映象名稱：
- `anoinex/banana-slides-frontend:latest`
- `anoinex/banana-slides-backend:latest`

**從頭構建映象**

```bash
docker compose up -d
```

> [!TIP]
> 如遇網路問題，可在 `.env` 檔案中取消映象源配置的註釋, 再重新執行啟動命令：
> ```env
> # 在 .env 檔案中取消以下注釋即可使用國內映象源
> DOCKER_REGISTRY=docker.1ms.run/
> GHCR_REGISTRY=ghcr.nju.edu.cn/
> APT_MIRROR=mirrors.aliyun.com
> PYPI_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
> NPM_REGISTRY=https://registry.npmmirror.com/
> ```


3. **訪問應用**

- 前端：http://localhost:3000
- 後端 API：http://localhost:5000

4. **檢視日誌**

```bash
# 檢視後端日誌（實時檢視最後50行）
sudo docker compose logs -f --tail 50 backend

# 檢視所有服務日誌（後200行）
sudo docker compose logs -f --tail 200

# 檢視前端日誌
sudo docker compose logs -f --tail 50 frontend
```

5. **停止服務**

```bash
docker compose down
```

6. **更新專案**

拉取最新程式碼並重新構建和啟動服務：

```bash
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

**注：感謝優秀開發者朋友 [@ShellMonster](https://github.com/ShellMonster/) 提供了[新人部署教程](https://github.com/ShellMonster/banana-slides/blob/docs-deploy-tutorial/docs/NEWBIE_DEPLOYMENT.md)，專為沒有任何伺服器部署經驗的新手設計，可[點選連結](https://github.com/ShellMonster/banana-slides/blob/docs-deploy-tutorial/docs/NEWBIE_DEPLOYMENT.md)檢視。**

### 從原始碼部署

#### 環境要求
- Python 3.10 或更高版本
- [uv](https://github.com/astral-sh/uv) - Python 包管理器
- Node.js 16+ 和 npm
- 有效的 Google Gemini API 金鑰

#### 後端安裝

0. **克隆程式碼倉庫**
```bash
git clone https://github.com/Anionex/banana-slides
cd banana-slides
```

1. **安裝 uv（如果尚未安裝）**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **安裝依賴**

在專案根目錄下執行：
```bash
uv sync
```

這將根據 `pyproject.toml` 自動安裝所有依賴。

3. **配置環境變數**

複製環境變數模板：
```bash
cp .env.example .env
```

編輯 `.env` 檔案，配置你的 API 金鑰：
> **專案中大模型介面以AIHubMix平臺格式為標準，推薦使用 [AIHubMix](https://aihubmix.com/?aff=17EC) 獲取API金鑰，減小遷移成本** 
```env
# AI Provider格式配置 (gemini / openai / vertex)
AI_PROVIDER_FORMAT=gemini

# Gemini 格式配置（當 AI_PROVIDER_FORMAT=gemini 時使用）
GOOGLE_API_KEY=your-api-key-here
GOOGLE_API_BASE=https://generativelanguage.googleapis.com
# 代理示例: https://aihubmix.com/gemini

# OpenAI 格式配置（當 AI_PROVIDER_FORMAT=openai 時使用）
OPENAI_API_KEY=your-api-key-here
OPENAI_API_BASE=https://api.openai.com/v1
# 代理示例: https://aihubmix.com/v1

# Vertex AI 格式配置（當 AI_PROVIDER_FORMAT=vertex 時使用）
# 需要 GCP 服務賬戶，可使用 GCP 免費額度
# VERTEX_PROJECT_ID=your-gcp-project-id
# VERTEX_LOCATION=global
# GOOGLE_APPLICATION_CREDENTIALS=./gcp-service-account.json

BACKEND_PORT=5000
...
```

#### 前端安裝

1. **進入前端目錄**
```bash
cd frontend
```

2. **安裝依賴**
```bash
npm install
```

3. **配置API地址**

前端會自動連線到 `http://localhost:5000` 的後端服務。如需修改，請編輯 `src/api/client.ts`。


#### 啟動後端服務
> （可選）如果本地已有重要資料，升級前建議先備份資料庫：  
> `cp backend/instance/database.db backend/instance/database.db.bak`

```bash
cd backend
uv run alembic upgrade head && uv run python app.py
```

後端服務將在 `http://localhost:5000` 啟動。

訪問 `http://localhost:5000/health` 驗證服務是否正常執行。

#### 啟動前端開發伺服器

```bash
cd frontend
npm run dev
```

前端開發伺服器將在 `http://localhost:3000` 啟動。

開啟瀏覽器訪問即可使用應用。


## 🛠️ 技術架構

### 前端技術棧
- **框架**：React 18 + TypeScript
- **構建工具**：Vite 5
- **狀態管理**：Zustand
- **路由**：React Router v6
- **UI元件**：Tailwind CSS
- **拖拽功能**：@dnd-kit
- **圖示**：Lucide React
- **HTTP客戶端**：Axios

### 後端技術棧
- **語言**：Python 3.10+
- **框架**：Flask 3.0
- **包管理**：uv
- **資料庫**：SQLite + Flask-SQLAlchemy
- **AI能力**：Google Gemini API
- **PPT處理**：python-pptx
- **圖片處理**：Pillow
- **併發處理**：ThreadPoolExecutor
- **跨域支援**：Flask-CORS

## 📁 專案結構

```
banana-slides/
├── frontend/                    # React前端應用
│   ├── src/
│   │   ├── pages/              # 頁面元件
│   │   │   ├── Home.tsx        # 首頁（建立專案）
│   │   │   ├── OutlineEditor.tsx    # 大綱編輯頁
│   │   │   ├── DetailEditor.tsx     # 詳細描述編輯頁
│   │   │   ├── SlidePreview.tsx     # 幻燈片預覽頁
│   │   │   └── History.tsx          # 歷史版本管理頁
│   │   ├── components/         # UI元件
│   │   │   ├── outline/        # 大綱相關元件
│   │   │   │   └── OutlineCard.tsx
│   │   │   ├── preview/        # 預覽相關元件
│   │   │   │   ├── SlideCard.tsx
│   │   │   │   └── DescriptionCard.tsx
│   │   │   ├── shared/         # 共享元件
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── Textarea.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Loading.tsx
│   │   │   │   ├── Toast.tsx
│   │   │   │   ├── Markdown.tsx
│   │   │   │   ├── MaterialSelector.tsx
│   │   │   │   ├── MaterialGeneratorModal.tsx
│   │   │   │   ├── TemplateSelector.tsx
│   │   │   │   ├── ReferenceFileSelector.tsx
│   │   │   │   └── ...
│   │   │   ├── layout/         # 佈局元件
│   │   │   └── history/        # 歷史版本元件
│   │   ├── store/              # Zustand狀態管理
│   │   │   └── useProjectStore.ts
│   │   ├── api/                # API介面
│   │   │   ├── client.ts       # Axios客戶端配置
│   │   │   └── endpoints.ts    # API端點定義
│   │   ├── types/              # TypeScript型別定義
│   │   ├── utils/              # 工具函式
│   │   ├── constants/          # 常量定義
│   │   └── styles/             # 樣式檔案
│   ├── public/                 # 靜態資源
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js      # Tailwind CSS配置
│   ├── Dockerfile
│   └── nginx.conf              # Nginx配置
│
├── backend/                    # Flask後端應用
│   ├── app.py                  # Flask應用入口
│   ├── config.py               # 配置檔案
│   ├── models/                 # 資料庫模型
│   │   ├── project.py          # Project模型
│   │   ├── page.py             # Page模型（幻燈片頁）
│   │   ├── task.py             # Task模型（非同步任務）
│   │   ├── material.py         # Material模型（參考素材）
│   │   ├── user_template.py    # UserTemplate模型（使用者模板）
│   │   ├── reference_file.py   # ReferenceFile模型（參考檔案）
│   │   ├── page_image_version.py # PageImageVersion模型（頁面版本）
│   ├── services/               # 服務層
│   │   ├── ai_service.py       # AI生成服務（Gemini整合）
│   │   ├── file_service.py     # 檔案管理服務
│   │   ├── file_parser_service.py # 檔案解析服務
│   │   ├── export_service.py   # PPTX/PDF匯出服務
│   │   ├── task_manager.py     # 非同步任務管理
│   │   ├── prompts.py          # AI提示詞模板
│   ├── controllers/            # API控制器
│   │   ├── project_controller.py      # 專案管理
│   │   ├── page_controller.py         # 頁面管理
│   │   ├── material_controller.py     # 素材管理
│   │   ├── template_controller.py     # 模板管理
│   │   ├── reference_file_controller.py # 參考檔案管理
│   │   ├── export_controller.py       # 匯出功能
│   │   └── file_controller.py         # 檔案上傳
│   ├── utils/                  # 工具函式
│   │   ├── response.py         # 統一響應格式
│   │   ├── validators.py       # 資料驗證
│   │   └── path_utils.py       # 路徑處理
│   ├── instance/               # SQLite資料庫（自動生成）
│   ├── exports/                # 匯出檔案目錄
│   ├── Dockerfile
│   └── README.md
│
├── tests/                      # 測試檔案目錄
├── v0_demo/                    # 早期演示版本
├── output/                     # 輸出檔案目錄
│
├── pyproject.toml              # Python專案配置（uv管理）
├── uv.lock                     # uv依賴鎖定檔案
├── docker-compose.yml          # Docker Compose配置
├── .env.example                 # 環境變數示例
├── LICENSE                     # 許可證
└── README.md                   # 本檔案
```


## 交流群
為了方便大家溝通互助，建此微信交流群.

歡迎提出新功能建議或反饋，本人也會~~佛系~~回答大家問題

<img width="301" alt="image" src="https://github.com/user-attachments/assets/56fb33bb-fab7-4625-a860-ecef09f41817" />



**常見問題**
1.  **支援免費層級的 Gemini API Key 嗎？**
    *   免費層級只支援文字生成，不支援圖片生成。
2.  **生成內容時提示 503 錯誤或 Retry Error**
    *   可以根據 README 中的命令檢視 Docker 內部日誌，定位 503 問題的詳細報錯，一般是模型配置不正確導致。
3.  **.env 中設定了 API Key 之後，為什麼不生效？**
    1.  執行時編輯.env需要重啟 Docker 容器以應用更改。
    2.  如果曾在網頁設定頁中設定，會覆蓋 `.env` 中引數，可透過“還原預設設定”還原到 `.env`。
4.  **生成頁面文字有亂碼**
    *   可以嘗試更高解析度的輸出（openai格式可能不支援調高解析度）
    *   確保在頁面描述中包含具體要渲染的文字內容
  

## 🤝 貢獻指南

歡迎透過
[Issue](https://github.com/Anionex/banana-slides/issues)
和
[Pull Request](https://github.com/Anionex/banana-slides/pulls)
為本專案貢獻力量！

## 📄 許可證

本專案採用 CC BY-NC-SA 4.0 協議進行開源，

可自由用於個人學習、研究、試驗、教育或非營利科研活動等非商業用途；

<details> 

<summary> 詳情 </summary>
本專案開源協議為非商業許可（CC BY-NC-SA），  
任何商業使用均需取得商業授權。

**商業使用**包括但不限於以下場景：

1. 企業或機構內部使用：

2. 對外服務：

3. 其他營利目的使用：

**非商業使用示例**（無需商業授權）：

- 個人學習、研究、試驗、教育或非營利科研活動；
- 開源社群貢獻、個人作品展示等不產生經濟收益的用途。

> 注：若對使用場景有疑問，請聯絡作者獲取授權許可。

</details>



<h2>🚀 Sponsor / 贊助 </h2>

<div align="center">
<a href="https://aihubmix.com/?aff=17EC">
  <img src="./assets/logo_aihubmix.png" alt="AIHubMix" style="height:48px;">
</a>
<p>感謝AIHubMix對本專案的贊助</p>
</div>


<div align="center">


 <img width="120" alt="image" src="https://github.com/user-attachments/assets/ac2ad6ec-c1cf-4aaa-859c-756b54168c96" />

<details>
  <summary>感謝<a href="https://api.chatfire.site/login?inviteCode=A15CD6A0">AI火寶</a>對本專案的贊助</summary>
  “聚合全球多模型API服務商。更低價格享受安全、穩定且72小時連結全球最新模型的服務。”
</details>

  
</div>



## 致謝

- 專案貢獻者們：

[![Contributors](https://contrib.rocks/image?repo=Anionex/banana-slides)](https://github.com/Anionex/banana-slides/graphs/contributors)

- [Linux.do](https://linux.do/): 新的理想型社群
  
## 讚賞

開源不易🙏如果本專案對你有價值，歡迎請開發者喝杯咖啡☕️

<img width="240" alt="image" src="https://github.com/user-attachments/assets/fd7a286d-711b-445e-aecf-43e3fe356473" />

感謝以下朋友對專案的無償贊助支援：
> @雅俗共賞、@曹崢、@以年觀日、@John、@胡yun星Ethan, @azazo1、@劉聰NLP、@🍟、@蒼何、@biubiu  
> 如對贊助列表有疑問（如讚賞後沒看到您的名字），可<a href="mailto:anionex@qq.com">聯絡作者</a>
 
## 📈 專案統計

<a href="https://www.star-history.com/#Anionex/banana-slides&type=Timeline&legend=top-left">

 <picture>

   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Anionex/banana-slides&type=Timeline&theme=dark&legend=top-left" />

   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Anionex/banana-slides&type=Timeline&legend=top-left" />

   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Anionex/banana-slides&type=Timeline&legend=top-left" />

 </picture>

</a>

<br>
