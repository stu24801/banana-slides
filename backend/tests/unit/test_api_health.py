"""
健康檢查API單元測試
"""

import pytest


class TestHealthEndpoint:
    """健康檢查端點測試"""
    
    def test_health_check_returns_ok(self, client):
        """測試健康檢查返回正常狀態"""
        response = client.get('/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        assert 'message' in data
    
    def test_health_check_response_format(self, client):
        """測試健康檢查響應格式"""
        response = client.get('/health')
        
        data = response.get_json()
        assert isinstance(data, dict)
        assert 'status' in data
        assert 'message' in data

