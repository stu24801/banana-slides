"""Database models package"""
from flask_sqlalchemy import SQLAlchemy

# 建立 SQLAlchemy 例項，配置 SQLite 連線選項
db = SQLAlchemy(
    engine_options={
        'connect_args': {
            'check_same_thread': False,  # 允許跨執行緒使用（僅SQLite）
            'timeout': 30,  # 資料庫鎖定超時（秒）- SQLite特定
        },
        'pool_pre_ping': True,  # 連線前檢查，確保連線有效
        'pool_recycle': 3600,  # 1小時回收連線，釋放檔案控制代碼
        'pool_size': 5,  # SQLite連線池不需要太大（建議5-10）
        'max_overflow': 10,  # 溢位連線數（SQLite受檔案鎖限制，不宜過大）
        'pool_timeout': 30,  # 獲取連線的超時時間（秒）
    }
)

from .project import Project
from .page import Page
from .task import Task
from .user_template import UserTemplate
from .page_image_version import PageImageVersion
from .material import Material
from .reference_file import ReferenceFile
from .settings import Settings

__all__ = ['db', 'Project', 'Page', 'Task', 'UserTemplate', 'PageImageVersion', 'Material', 'ReferenceFile', 'Settings']

