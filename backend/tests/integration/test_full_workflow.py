"""
完整工作流整合測試

測試從建立專案到匯出PPTX的完整流程
"""

import pytest
import time
from conftest import assert_success_response


class TestFullWorkflow:
    """完整工作流測試"""
    
    def test_create_project_and_get_details(self, client):
        """測試建立專案並獲取詳情"""
        # 1. 建立專案
        create_response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生成一份關於量子計算的PPT，共3頁'
        })
        
        data = assert_success_response(create_response, 201)
        project_id = data['data']['project_id']
        
        # 2. 獲取專案詳情
        get_response = client.get(f'/api/projects/{project_id}')
        
        data = assert_success_response(get_response)
        assert data['data']['project_id'] == project_id
        assert data['data']['status'] == 'DRAFT'
    
    def test_template_upload_workflow(self, client, sample_image_file):
        """測試模板上傳工作流"""
        # 1. 建立專案
        create_response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '測試模板上傳'
        })
        
        data = assert_success_response(create_response, 201)
        project_id = data['data']['project_id']
        
        # 2. 上傳模板
        upload_response = client.post(
            f'/api/projects/{project_id}/template',
            data={'template_image': (sample_image_file, 'template.png')},
            content_type='multipart/form-data'
        )
        
        # 檢查上傳結果
        assert upload_response.status_code in [200, 201]
    
    def test_project_lifecycle(self, client):
        """測試專案完整生命週期"""
        # 1. 建立
        create_response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生命週期測試'
        })
        data = assert_success_response(create_response, 201)
        project_id = data['data']['project_id']
        
        # 2. 讀取
        get_response = client.get(f'/api/projects/{project_id}')
        assert_success_response(get_response)
        
        # 3. 更新（如果API支援）
        # update_response = client.put(f'/api/projects/{project_id}', json={...})
        
        # 4. 刪除
        delete_response = client.delete(f'/api/projects/{project_id}')
        assert_success_response(delete_response)
        
        # 5. 確認刪除
        verify_response = client.get(f'/api/projects/{project_id}')
        assert verify_response.status_code == 404


class TestAPIErrorHandling:
    """API錯誤處理測試"""
    
    def test_invalid_json_body(self, client):
        """測試無效的JSON請求體"""
        response = client.post(
            '/api/projects',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code in [400, 415, 422]
    
    def test_missing_required_fields(self, client):
        """測試缺少必需欄位"""
        response = client.post('/api/projects', json={})
        
        assert response.status_code in [400, 422]
    
    def test_method_not_allowed(self, client):
        """測試不允許的HTTP方法"""
        response = client.patch('/api/projects')
        
        # PATCH可能不被支援
        assert response.status_code in [404, 405]


class TestConcurrentRequests:
    """併發請求測試"""
    
    def test_multiple_project_creation(self, client):
        """測試多個專案建立不衝突"""
        project_ids = []
        
        for i in range(3):
            response = client.post('/api/projects', json={
                'creation_type': 'idea',
                'idea_prompt': f'併發測試專案 {i}'
            })
            
            data = assert_success_response(response, 201)
            project_ids.append(data['data']['project_id'])
        
        # 確保所有專案ID都不同
        assert len(set(project_ids)) == 3
        
        # 清理
        for pid in project_ids:
            client.delete(f'/api/projects/{pid}')

