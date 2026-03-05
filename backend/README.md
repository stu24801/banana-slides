# Banana Slides Backend

蕉幻（Banana Slides）後端服務 - AI驅動的PPT生成系統

## 技術棧

- **框架**: Flask 3.0
- **資料庫**: SQLite + SQLAlchemy ORM
- **AI服務**: Google Gemini API
- **PPT處理**: python-pptx
- **併發處理**: ThreadPoolExecutor
- **包管理**: uv

## 專案結構

```
backend/
├── app.py                    # Flask應用入口
├── config.py                 # 配置檔案
├── models/                   # 資料庫模型
│   ├── __init__.py
│   ├── project.py           # Project模型
│   ├── page.py              # Page模型
│   └── task.py              # Task模型
├── services/                 # 服務層
│   ├── __init__.py
│   ├── ai_service.py        # AI相關服務
│   ├── file_service.py      # 檔案管理服務
│   ├── export_service.py    # 匯出服務
│   └── task_manager.py      # 非同步任務管理
├── controllers/              # 控制器層
│   ├── __init__.py
│   ├── project_controller.py
│   ├── page_controller.py
│   ├── template_controller.py
│   ├── export_controller.py
│   └── file_controller.py
├── utils/                    # 工具函式
│   ├── __init__.py
│   ├── response.py          # 統一響應格式
│   └── validators.py        # 資料驗證
├── instance/                 # 資料庫檔案目錄（自動建立）
├── uploads/                  # 檔案上傳目錄（自動建立）
├── .env.example             # 環境變數示例
└── README.md                # 本檔案
```

## 快速開始

### 1. 安裝依賴

本專案使用 [uv](https://github.com/astral-sh/uv) 管理 Python 依賴。所有依賴定義在專案根目錄的 `pyproject.toml` 檔案中。

在專案根目錄下執行：
```bash
uv sync
```

這將自動安裝所有必需的依賴包。

### 2. 配置環境變數

複製 `.env.example` 為 `.env` 並填寫配置：

```bash
cp .env.example .env
```

編輯 `.env` 檔案：

```env
GOOGLE_API_KEY=your-google-api-key
GOOGLE_API_BASE=https://generativelanguage.googleapis.com

# 火山引擎配置（可選，用於 Inpainting 影象消除功能）
VOLCENGINE_ACCESS_KEY=your-volcengine-access-key
VOLCENGINE_SECRET_KEY=your-volcengine-secret-key
VOLCENGINE_INPAINTING_TIMEOUT=60
VOLCENGINE_INPAINTING_MAX_RETRIES=3
```

### 3. 初始化 / 升級資料庫結構（Alembic 遷移）

從當前版本開始，後端使用 Alembic 管理資料庫結構變更。

```bash
cd backend
uv run alembic upgrade head
```

> 注意：  
> - 首次執行時會自動建立 `alembic_version` 表並將資料庫遷移到最新結構；  
> - 後續新增模型欄位時，只需要更新 `models/`，然後使用 `alembic revision --autogenerate` 生成遷移，再執行 `alembic upgrade head`。

### 4. 執行服務

使用 uv 執行：
```bash
cd backend
uv run python app.py
```
服務將在 `http://localhost:5000` 啟動。

## API文件

完整的API文件請參考專案根目錄的 `API設計文件.md`。

### 主要端點

#### 專案管理
- `POST /api/projects` - 建立專案
- `GET /api/projects/{project_id}` - 獲取專案詳情
- `PUT /api/projects/{project_id}` - 更新專案
- `DELETE /api/projects/{project_id}` - 刪除專案

#### 大綱生成
- `POST /api/projects/{project_id}/generate/outline` - 生成大綱

#### 描述生成
- `POST /api/projects/{project_id}/generate/descriptions` - 批次生成描述（非同步）
- `POST /api/projects/{project_id}/pages/{page_id}/generate/description` - 單頁生成

#### 圖片生成
- `POST /api/projects/{project_id}/generate/images` - 批次生成圖片（非同步）
- `POST /api/projects/{project_id}/pages/{page_id}/generate/image` - 單頁生成
- `POST /api/projects/{project_id}/pages/{page_id}/edit/image` - 編輯圖片

#### 模板管理
- `POST /api/projects/{project_id}/template` - 上傳模板
- `DELETE /api/projects/{project_id}/template` - 刪除模板

#### 匯出
- `GET /api/projects/{project_id}/export/pptx` - 匯出PPTX
- `GET /api/projects/{project_id}/export/pdf` - 匯出PDF

#### 靜態檔案
- `GET /files/{project_id}/{type}/{filename}` - 獲取檔案

## 核心功能

### 1. AI驅動的內容生成

基於 Google Gemini API，支援：
- 自動生成PPT大綱
- 並行生成頁面描述
- 根據參考模板生成圖片
- 自然語言編輯圖片

### 2. 非同步任務處理

使用 `ThreadPoolExecutor` 實現簡單但高效的非同步任務處理：
- 並行生成多個頁面描述
- 並行生成多個頁面圖片
- 實時任務進度跟蹤

### 3. 檔案管理

完整的檔案管理系統：
- 專案級檔案隔離
- 模板圖片管理
- 生成圖片管理
- 自動清理機制

### 4. Inpainting 影象消除（可選）

基於火山引擎的 Inpainting 服務，支援：
- 根據邊界框（bbox）精確消除影象區域
- 自動生成掩碼影象
- 重新生成背景（保留前景，消除其他區域）
- 支援批次處理和重試機制

使用方法：
```python
from services.inpainting_service import InpaintingService, remove_regions
from PIL import Image

# 方式1：使用服務類
service = InpaintingService()
image = Image.open('original.png')
bboxes = [(100, 100, 200, 200), (300, 150, 400, 250)]  # 要消除的區域
result = service.remove_regions_by_bboxes(image, bboxes)

# 方式2：使用便捷函式
result = remove_regions(image, bboxes, expand_pixels=5)
```

### 5. 資料持久化

使用 SQLite + SQLAlchemy：
- 輕量級，無需額外配置
- 支援關係型資料操作
- 事務保證資料一致性

## 開發說明

### 資料模型

#### Project（專案）
- 專案基本資訊
- 模板圖片路徑
- 專案狀態
- 關聯的頁面和任務

#### Page（頁面）
- 頁面順序
- 大綱內容（JSON）
- 描述內容（JSON）
- 生成的圖片路徑
- 頁面狀態

#### Task（任務）
- 任務型別（生成描述/生成圖片）
- 任務狀態
- 進度資訊（JSON）
- 錯誤資訊

### 狀態機

#### 專案狀態
```
DRAFT → OUTLINE_GENERATED → DESCRIPTIONS_GENERATED → GENERATING_IMAGES → COMPLETED
```

#### 頁面狀態
```
DRAFT → DESCRIPTION_GENERATED → GENERATING → COMPLETED | FAILED
```

#### 任務狀態
```
PENDING → PROCESSING → COMPLETED | FAILED
```

### 擴充套件開發

#### 新增新的AI模型

在 `services/ai_service.py` 中新增新的模型支援：

```python
class AIService:
    def __init__(self, api_key: str, model_type: str = 'gemini'):
        if model_type == 'gemini':
            # Gemini implementation
        elif model_type == 'openai':
            # OpenAI implementation
        # ...
```

#### 自定義提示詞模板

修改 `services/ai_service.py` 中的提示詞生成邏輯：

```python
def generate_image_prompt(self, ...):
    prompt = dedent(f"""
        # 自定義提示詞模板
        ...
    """)
    return prompt
```

#### 新增新的匯出格式

在 `services/export_service.py` 中新增新的匯出方法：

```python
class ExportService:
    @staticmethod
    def create_custom_format(image_paths, output_file):
        # 實現自定義格式匯出
        pass
```


## 測試

### 健康檢查

```bash
curl http://localhost:5000/health
```

### 建立專案

```bash
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"creation_type":"idea","idea_prompt":"生成環保主題ppt"}'
```

### 上傳模板

```bash
curl -X POST http://localhost:5000/api/projects/{project_id}/template \
  -F "template_image=@template.png"
```

### 生成大綱

```bash
curl -X POST http://localhost:5000/api/projects/{project_id}/generate/outline \
  -H "Content-Type: application/json" \
  -d '{"idea_prompt":"生成環保主題ppt"}'
```

## 常見問題

### Q: 資料庫檔案在哪裡？
A: 在 `backend/instance/database.db`，會自動建立。

### Q: 上傳的檔案存在哪裡？
A: 在 `uploads/{project_id}/` 目錄下，按專案隔離。

### Q: 如何修改併發數？
A: 推薦透過前端設定頁修改（會同步到資料庫並覆蓋 `.env` 值）；也可以在 `.env` 檔案中修改 `MAX_DESCRIPTION_WORKERS` 和 `MAX_IMAGE_WORKERS` 作為預設值，然後在設定頁點選“重置為預設值”同步到 DB。

### Q: 如何切換到其他AI模型 / 修改 MinerU 地址？
A: 從當前版本開始，推薦透過前端“系統設定”頁面修改：  
- 大模型提供商格式 / API Base / API Key  
- 文字模型 (`TEXT_MODEL`) / 圖片模型 (`IMAGE_MODEL`)  
- MinerU 地址 (`MINERU_API_BASE`) / 圖片識別模型 (`IMAGE_CAPTION_MODEL`)  

這些值會儲存到 `settings` 表並覆蓋 `.env` 中對應配置，點選“重置為預設值”會回到 `.env` 的預設值。

### Q: 支援哪些圖片格式？
A: PNG, JPG, JPEG, GIF, WEBP。在 `config.py` 中的 `ALLOWED_EXTENSIONS` 配置。


## 開源字型說明

本專案包含 **Noto Sans CJK SC**（思源黑體簡體中文）字型檔案，用於 PPT 匯出時的精確文字測量。

- **字型檔案**: `fonts/NotoSansSC-Regular.ttf`
- **來源**: [Google Noto CJK Fonts](https://github.com/googlefonts/noto-cjk)
- **許可證**: [SIL Open Font License 1.1 (OFL)](https://scripts.sil.org/OFL)

OFL 許可證允許自由使用、修改和分發該字型。

## 聯絡方式

如有問題或建議，請透過 GitHub Issues 反饋。

