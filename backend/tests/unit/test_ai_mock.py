"""
AI服務Mock測試

驗證AI服務被正確mock，不會真正呼叫外部API
"""

import pytest
from unittest.mock import patch, MagicMock


class TestAIMock:
    """AI Mock測試"""
    
    def test_ai_service_is_mocked(self, mock_ai_service):
        """驗證AI服務被正確mock"""
        # 呼叫mock的方法
        outline = mock_ai_service.generate_outline("測試prompt")
        
        # 驗證返回mock資料
        assert len(outline) == 2
        assert outline[0]['title'] == '測試頁面1'
        
        # 驗證方法被呼叫
        mock_ai_service.generate_outline.assert_called_once_with("測試prompt")
    
    def test_description_generation_mocked(self, mock_ai_service):
        """驗證描述生成被mock"""
        desc = mock_ai_service.generate_page_description(
            "idea", [], {}, 1
        )
        
        assert desc['title'] == '測試標題'
        assert 'text_content' in desc
    
    def test_image_generation_mocked(self, mock_ai_service):
        """驗證圖片生成被mock"""
        image = mock_ai_service.generate_image("prompt", "ref.png")
        
        # 應該返回一個PIL Image物件
        assert image is not None
        assert image.size == (1920, 1080)
    
    def test_no_real_api_calls(self, mock_ai_service):
        """確保沒有真實API呼叫"""
        # 多次呼叫
        for _ in range(10):
            mock_ai_service.generate_outline("test")
            mock_ai_service.generate_page_description("idea", [], {}, 1)
        
        # 驗證呼叫次數
        assert mock_ai_service.generate_outline.call_count == 10
        assert mock_ai_service.generate_page_description.call_count == 10


class TestEnvironmentFlags:
    """環境標誌測試"""
    
    def test_testing_flag_is_set(self):
        """驗證測試標誌已設定"""
        import os
        assert os.environ.get('TESTING') == 'true'
    
    def test_mock_ai_flag_is_set(self):
        """驗證mock AI標誌已設定"""
        import os
        assert os.environ.get('USE_MOCK_AI') == 'true'

