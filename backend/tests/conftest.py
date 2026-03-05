"""
pytest配置檔案 - 提供測試fixtures和配置

用於後端所有測試的共享配置和fixtures
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# 確保backend目錄在Python路徑中
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# 設定測試環境變數 - 必須在匯入app之前設定
os.environ['TESTING'] = 'true'
os.environ['USE_MOCK_AI'] = 'true'  # 標記使用mock AI服務
os.environ['GOOGLE_API_KEY'] = os.environ.get('GOOGLE_API_KEY', 'mock-api-key-for-testing')
os.environ['FLASK_ENV'] = 'testing'


@pytest.fixture(scope='session')
def app():
    """建立Flask測試應用"""
    # 建立臨時目錄用於測試
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, 'test.db')
    
    # 設定測試資料庫路徑
    os.environ['DATABASE_URL'] = f'sqlite:///{temp_db}'
    
    # 現在匯入app
    from app import create_app
    
    # 使用工廠函式建立測試應用
    test_app = create_app()
    
    # 覆蓋配置
    test_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{temp_db}',
        'WTF_CSRF_ENABLED': False,
        'UPLOAD_FOLDER': temp_dir,
    })
    
    # 建立應用上下文
    with test_app.app_context():
        from models import db
        db.create_all()
    
    yield test_app
    
    # 清理
    import shutil
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture(scope='function')
def client(app):
    """建立測試客戶端"""
    with app.test_client() as test_client:
        with app.app_context():
            from models import db
            # 清理舊資料，保持測試隔離
            db.session.rollback()
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(table.delete())
            db.session.commit()
            yield test_client
            db.session.rollback()


@pytest.fixture(scope='function')
def db_session(app):
    """建立資料庫會話"""
    with app.app_context():
        from models import db
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_project(client):
    """建立示例專案"""
    response = client.post('/api/projects', 
        json={
            'creation_type': 'idea',
            'idea_prompt': '測試PPT生成'
        }
    )
    data = response.get_json()
    return data['data'] if data.get('success') else None


@pytest.fixture
def mock_ai_service():
    """Mock AI服務，避免真實API呼叫（使用標準庫unittest.mock）"""
    with patch('services.ai_service.AIService') as mock:
        # Mock例項
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        
        # Mock大綱生成
        mock_instance.generate_outline.return_value = [
            {'title': '測試頁面1', 'points': ['要點1', '要點2']},
            {'title': '測試頁面2', 'points': ['要點3', '要點4']},
        ]
        
        # Mock扁平化大綱
        mock_instance.flatten_outline.return_value = [
            {'title': '測試頁面1', 'points': ['要點1', '要點2']},
            {'title': '測試頁面2', 'points': ['要點3', '要點4']},
        ]
        
        # Mock描述生成
        mock_instance.generate_page_description.return_value = {
            'title': '測試標題',
            'text_content': ['內容1', '內容2'],
            'layout_suggestion': '居中佈局'
        }
        
        # Mock圖片生成 - 返回一個簡單的測試圖片
        from PIL import Image
        test_image = Image.new('RGB', (1920, 1080), color='blue')
        mock_instance.generate_image.return_value = test_image
        
        yield mock_instance


@pytest.fixture
def temp_upload_dir():
    """建立臨時上傳目錄"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_image_file():
    """建立示例圖片檔案"""
    # 建立一個簡單的PNG檔案（1x1畫素的紅色圖片）
    import io
    from PIL import Image
    
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


# =====================================
# 測試工具函式
# =====================================

def assert_success_response(response, status_code=200):
    """斷言成功響應"""
    assert response.status_code == status_code
    data = response.get_json()
    assert data is not None
    assert data.get('success') is True
    return data


def assert_error_response(response, expected_status=None):
    """斷言錯誤響應"""
    if expected_status:
        assert response.status_code == expected_status
    data = response.get_json()
    assert data is not None
    assert data.get('success') is False or 'error' in data
    return data

