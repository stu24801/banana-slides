# Backend Integration Tests

## 測試分類

### 1. Flask Test Client 測試（不需要執行服務）
**檔案**: `test_full_workflow.py`

這些測試使用 Flask 的測試客戶端（`client` fixture），不需要真實的服務執行。

**特點**：
- ✅ 快速（毫秒級）
- ✅ 不需要啟動服務
- ✅ 在 CI 的 `backend-integration-test` 階段執行
- ✅ 使用 mock 模式，不需要真實 API key

**執行方式**：
```bash
cd backend
uv run pytest tests/integration/test_full_workflow.py -v
```

### 2. Real Service 測試（需要執行服務）
**檔案**: `test_api_full_flow.py`

這些測試使用 `requests` 庫直接呼叫 HTTP 端點，需要真實的後端服務執行。

**特點**：
- ⏱️ 較慢（需要真實 HTTP 請求）
- 🔧 需要服務執行在 `http://localhost:5000`
- 🏗️ 在 CI 的 `docker-test` 階段執行（服務已啟動）
- 🔑 完整流程測試需要真實 AI API key

**標記**: `@pytest.mark.requires_service`

**執行方式**：
```bash
# 1. 啟動服務
docker compose up -d

# 2. 執行測試
cd backend
uv run pytest tests/integration/test_api_full_flow.py -v -m "requires_service"
```

## CI/CD 策略

### Backend Integration Test 階段
**何時執行**: 在每次 PR 和 push 時

**執行測試**: 
- ✅ 使用 Flask test client 的測試
- ❌ 跳過需要真實服務的測試

```yaml
# 跳過 @pytest.mark.requires_service 標記的測試
pytest tests/integration -v -m "not requires_service"
```

**環境變數**:
```yaml
TESTING: true
SKIP_SERVICE_TESTS: true
GOOGLE_API_KEY: mock-api-key-for-testing
```

### Docker Test 階段
**何時執行**: 在 PR 新增 `ready-for-test` 標籤時

**執行測試**:
- ✅ 執行需要真實服務的測試
- ✅ 測試完整的 API 呼叫流程

```yaml
# 只執行 @pytest.mark.requires_service 標記的測試
pytest tests/integration/test_api_full_flow.py -v -m "requires_service"
```

**環境變數**:
```yaml
SKIP_SERVICE_TESTS: false
GOOGLE_API_KEY: <real-api-key-from-secrets>
```

## Pytest Markers

所有可用的 markers 定義在 `pytest.ini` 中：

| Marker | 說明 | 示例 |
|--------|------|------|
| `unit` | 單元測試 | 測試單個函式或方法 |
| `integration` | 整合測試 | 測試多個元件互動 |
| `slow` | 慢速測試 | 需要 AI API 呼叫的測試 |
| `requires_service` | 需要執行服務 | 使用 requests 呼叫 HTTP 端點 |
| `mock` | 使用 mock | 不呼叫真實外部服務 |
| `docker` | Docker 環境測試 | 需要 Docker 環境 |

## 執行示例

### 執行所有整合測試（跳過需要服務的）
```bash
cd backend
SKIP_SERVICE_TESTS=true uv run pytest tests/integration/ -v -m "not requires_service"
```

### 只執行需要服務的測試
```bash
# 確保服務已啟動
docker compose up -d

# 執行測試
cd backend
SKIP_SERVICE_TESTS=false uv run pytest tests/integration/ -v -m "requires_service"
```

### 執行所有整合測試（需要服務）
```bash
# 確保服務已啟動
docker compose up -d

# 執行所有測試
cd backend
uv run pytest tests/integration/ -v
```

### 執行特定測試
```bash
# 執行快速 API 測試（需要服務）
cd backend
uv run pytest tests/integration/test_api_full_flow.py::TestAPIFullFlow::test_quick_api_flow_no_ai -v

# 執行完整流程測試（需要服務和真實 API key）
cd backend
uv run pytest tests/integration/test_api_full_flow.py::TestAPIFullFlow::test_api_full_flow_create_to_export -v
```

## 故障排除

### 問題：`ConnectionRefusedError: [Errno 111] Connection refused`

**原因**: 測試嘗試連線 `localhost:5000`，但服務未執行。

**解決方案**:
1. 啟動服務：`docker compose up -d`
2. 或者跳過這些測試：`pytest -m "not requires_service"`

### 問題：測試在 CI 的 backend-integration-test 階段失敗

**原因**: 該階段不啟動服務，應該跳過 `requires_service` 測試。

**解決方案**: 確保 CI 配置使用了正確的 pytest 命令：
```yaml
pytest tests/integration -v -m "not requires_service"
```

## 最佳實踐

1. **新的整合測試**:
   - 如果測試可以使用 Flask test client → 新增到 `test_full_workflow.py`
   - 如果測試需要真實 HTTP 呼叫 → 新增到 `test_api_full_flow.py` 並標記 `@pytest.mark.requires_service`

2. **Marker 使用**:
   ```python
   @pytest.mark.integration
   @pytest.mark.requires_service
   def test_real_api_call(self):
       response = requests.post('http://localhost:5000/api/projects', ...)
   ```

3. **環境檢查**:
   - 檔案級跳過：使用 `pytestmark = pytest.mark.skipif(...)`
   - 測試級跳過：使用 `@pytest.mark.skipif(...)`

---

**更新日期**: 2025-12-22  
**維護者**: Banana Slides Team

