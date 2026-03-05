"""
Backend configuration file
"""
import os
import sys
from datetime import timedelta

# 基礎配置 - 使用更可靠的路徑計算方式
# 在模組載入時立即計算並固定路徑
_current_file = os.path.realpath(__file__)  # 使用realpath解析所有符號連結
BASE_DIR = os.path.dirname(_current_file)
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Flask配置
class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    
    # 資料庫配置
    # Use absolute path to avoid WSL path issues
    db_path = os.path.join(BASE_DIR, 'instance', 'database.db')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', 
        f'sqlite:///{db_path}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLite執行緒安全配置 - 關鍵修復
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'check_same_thread': False,  # 允許跨執行緒使用（僅SQLite）
            'timeout': 30  # 增加超時時間
        },
        'pool_pre_ping': True,  # 連線前檢查
        'pool_recycle': 3600,  # 1小時回收連線
    }
    
    # 檔案儲存配置
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_REFERENCE_FILE_EXTENSIONS = {'pdf', 'docx', 'pptx', 'doc', 'ppt', 'xlsx', 'xls', 'csv', 'txt', 'md'}
    
    # AI服務配置
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
    GOOGLE_API_BASE = os.getenv('GOOGLE_API_BASE', '')
    
    # AI Provider 格式配置: "gemini" (Google GenAI SDK), "openai" (OpenAI SDK), "vertex" (Vertex AI)
    AI_PROVIDER_FORMAT = os.getenv('AI_PROVIDER_FORMAT', 'gemini')

    # Vertex AI 專用配置（當 AI_PROVIDER_FORMAT=vertex 時使用）
    VERTEX_PROJECT_ID = os.getenv('VERTEX_PROJECT_ID', '')
    VERTEX_LOCATION = os.getenv('VERTEX_LOCATION', 'us-central1')
    
    # GenAI (Gemini) 格式專用配置
    GENAI_TIMEOUT = float(os.getenv('GENAI_TIMEOUT', '300.0'))  # Gemini 超時時間（秒）
    GENAI_MAX_RETRIES = int(os.getenv('GENAI_MAX_RETRIES', '2'))  # Gemini 最大重試次數（應用層實現）
    
    # OpenAI 格式專用配置（當 AI_PROVIDER_FORMAT=openai 時使用）
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')  # 當 AI_PROVIDER_FORMAT=openai 時必須設定
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://aihubmix.com/v1')
    OPENAI_TIMEOUT = float(os.getenv('OPENAI_TIMEOUT', '300.0'))  # 增加到 5 分鐘（生成清潔背景圖需要很長時間）
    OPENAI_MAX_RETRIES = int(os.getenv('OPENAI_MAX_RETRIES', '2'))  # 減少重試次數，避免過多重試導致累積超時
    
    # AI 模型配置
    TEXT_MODEL = os.getenv('TEXT_MODEL', 'gemini-3-flash-preview')
    IMAGE_MODEL = os.getenv('IMAGE_MODEL', 'gemini-3-pro-image-preview')

    # MinerU 檔案解析服務配置
    MINERU_TOKEN = os.getenv('MINERU_TOKEN', '')
    MINERU_API_BASE = os.getenv('MINERU_API_BASE', 'https://mineru.net')
    
    # 圖片識別模型配置
    IMAGE_CAPTION_MODEL = os.getenv('IMAGE_CAPTION_MODEL', 'gemini-3-flash-preview')
    
    # 併發配置
    MAX_DESCRIPTION_WORKERS = int(os.getenv('MAX_DESCRIPTION_WORKERS', '5'))
    MAX_IMAGE_WORKERS = int(os.getenv('MAX_IMAGE_WORKERS', '8'))
    
    # 圖片生成配置
    DEFAULT_ASPECT_RATIO = "16:9"
    DEFAULT_RESOLUTION = "2K"
    
    # 日誌配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # CORS配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
    
    # 輸出語言配置
    # 可選值: 'zh' (中文), 'ja' (日本語), 'en' (English), 'auto' (自動)
    OUTPUT_LANGUAGE = os.getenv('OUTPUT_LANGUAGE', 'zh')
    
    # 火山引擎配置
    VOLCENGINE_ACCESS_KEY = os.getenv('VOLCENGINE_ACCESS_KEY', '')
    VOLCENGINE_SECRET_KEY = os.getenv('VOLCENGINE_SECRET_KEY', '')
    VOLCENGINE_INPAINTING_TIMEOUT = int(os.getenv('VOLCENGINE_INPAINTING_TIMEOUT', '60'))  # Inpainting 超時時間（秒）
    VOLCENGINE_INPAINTING_MAX_RETRIES = int(os.getenv('VOLCENGINE_INPAINTING_MAX_RETRIES', '3'))  # 最大重試次數

    # Inpainting Provider 配置（用於 InpaintingService 的單張圖片修復）
    # 可選值: 'volcengine' (火山引擎), 'gemini' (Google Gemini)
    # 注意: 可編輯PPTX匯出功能使用 ImageEditabilityService，其中 HybridInpaintProvider 會結合百度重繪和生成式質量增強
    INPAINTING_PROVIDER = os.getenv('INPAINTING_PROVIDER', 'gemini')  # 預設使用 Gemini
    
    # 百度 API 配置（用於 OCR 和影象修復）
    BAIDU_OCR_API_KEY = os.getenv('BAIDU_OCR_API_KEY', '')
    BAIDU_OCR_API_SECRET = os.getenv('BAIDU_OCR_API_SECRET', '')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


# 根據環境變數選擇配置
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)
