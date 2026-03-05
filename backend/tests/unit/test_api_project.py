"""
專案管理API單元測試
"""

import pytest
from conftest import assert_success_response, assert_error_response


class TestProjectCreate:
    """專案建立測試"""
    
    def test_create_project_idea_mode(self, client):
        """測試從想法建立專案"""
        response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生成一份關於AI的PPT'
        })
        
        data = assert_success_response(response, 201)
        assert 'project_id' in data['data']
        assert data['data']['status'] == 'DRAFT'
    
    def test_create_project_outline_mode(self, client):
        """測試從大綱建立專案"""
        response = client.post('/api/projects', json={
            'creation_type': 'outline',
            'outline': [
                {'title': '第一頁', 'points': ['要點1']},
                {'title': '第二頁', 'points': ['要點2']}
            ]
        })
        
        data = assert_success_response(response, 201)
        assert 'project_id' in data['data']
    
    def test_create_project_missing_type(self, client):
        """測試缺少creation_type引數"""
        response = client.post('/api/projects', json={
            'idea_prompt': '測試'
        })
        
        # 應該返回錯誤
        assert response.status_code in [400, 422]
    
    def test_create_project_invalid_type(self, client):
        """測試無效的creation_type"""
        response = client.post('/api/projects', json={
            'creation_type': 'invalid_type',
            'idea_prompt': '測試'
        })
        
        assert response.status_code in [400, 422]


class TestProjectGet:
    """專案獲取測試"""
    
    def test_get_project_success(self, client, sample_project):
        """測試獲取專案成功"""
        if not sample_project:
            pytest.skip("專案建立失敗")
        
        project_id = sample_project['project_id']
        response = client.get(f'/api/projects/{project_id}')
        
        data = assert_success_response(response)
        assert data['data']['project_id'] == project_id
    
    def test_get_project_not_found(self, client):
        """測試獲取不存在的專案"""
        response = client.get('/api/projects/non-existent-id')
        
        assert response.status_code == 404
    
    def test_get_project_invalid_id_format(self, client):
        """測試無效的專案ID格式"""
        response = client.get('/api/projects/invalid!@#$%id')
        
        # 可能返回404或400
        assert response.status_code in [400, 404]


class TestProjectUpdate:
    """專案更新測試"""
    
    def test_update_project_status(self, client, sample_project):
        """測試更新專案狀態"""
        if not sample_project:
            pytest.skip("專案建立失敗")
        
        project_id = sample_project['project_id']
        response = client.put(f'/api/projects/{project_id}', json={
            'status': 'GENERATING'
        })
        
        # 狀態更新應該成功
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True


class TestProjectDelete:
    """專案刪除測試"""
    
    def test_delete_project_success(self, client, sample_project):
        """測試刪除專案成功"""
        if not sample_project:
            pytest.skip("專案建立失敗")
        
        project_id = sample_project['project_id']
        response = client.delete(f'/api/projects/{project_id}')
        
        data = assert_success_response(response)
        
        # 確認專案已刪除
        get_response = client.get(f'/api/projects/{project_id}')
        assert get_response.status_code == 404
    
    def test_delete_project_not_found(self, client):
        """測試刪除不存在的專案"""
        response = client.delete('/api/projects/non-existent-id')
        
        assert response.status_code == 404

