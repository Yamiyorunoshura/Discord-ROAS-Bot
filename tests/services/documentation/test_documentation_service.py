"""
文檔服務測試
Task ID: 11 - 建立文件和部署準備

測試文檔生成、版本管理和品質驗證功能
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from services.documentation.documentation_service import DocumentationService
from services.documentation.models import (
    DocumentConfig, DocumentCategory, DocumentFormat, 
    DocumentStatus, DocumentValidationResult
)
from core.database_manager import DatabaseManager
from test_utils.discord_mocks import MockBot


class TestDocumentationService:
    """文檔服務測試類"""
    
    @pytest.fixture
    async def temp_docs_dir(self):
        """創建臨時文檔目錄"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    async def mock_db_manager(self):
        """模擬資料庫管理器"""
        mock_db = AsyncMock(spec=DatabaseManager)
        mock_db.execute = AsyncMock()
        mock_db.fetch_all = AsyncMock(return_value=[])
        mock_db.fetch_one = AsyncMock(return_value=None)
        return mock_db
    
    @pytest.fixture
    async def documentation_service(self, mock_db_manager, temp_docs_dir):
        """創建文檔服務實例"""
        service = DocumentationService(mock_db_manager)
        service.docs_root_path = temp_docs_dir
        service.api_docs_path = temp_docs_dir / "api"
        service.user_docs_path = temp_docs_dir / "user"
        service.technical_docs_path = temp_docs_dir / "technical"
        service.templates_path = temp_docs_dir / "templates"
        return service
    
    @pytest.mark.unit
    async def test_service_initialization(self, documentation_service, mock_db_manager):
        """測試服務初始化"""
        # 準備
        mock_db_manager.execute = AsyncMock()
        mock_db_manager.fetch_all = AsyncMock(return_value=[])
        
        # 執行
        result = await documentation_service.initialize()
        
        # 驗證
        assert result is True
        assert documentation_service.is_initialized
        
        # 驗證目錄創建
        assert documentation_service.docs_root_path.exists()
        assert documentation_service.api_docs_path.exists()
        assert documentation_service.user_docs_path.exists()
        assert documentation_service.technical_docs_path.exists()
        
        # 驗證資料庫初始化
        assert mock_db_manager.execute.call_count >= 2
    
    @pytest.mark.unit
    async def test_directory_structure_creation(self, documentation_service):
        """測試目錄結構創建"""
        # 執行
        await documentation_service._create_directory_structure()
        
        # 驗證
        expected_dirs = [
            documentation_service.docs_root_path,
            documentation_service.api_docs_path,
            documentation_service.user_docs_path,
            documentation_service.technical_docs_path,
            documentation_service.templates_path,
            documentation_service.docs_root_path / "architecture",
            documentation_service.docs_root_path / "developer",
            documentation_service.docs_root_path / "troubleshooting"
        ]
        
        for directory in expected_dirs:
            assert directory.exists(), f"目錄 {directory} 未創建"
    
    @pytest.mark.unit
    async def test_save_document(self, documentation_service, mock_db_manager):
        """測試文檔儲存"""
        # 準備
        await documentation_service._create_directory_structure()
        mock_db_manager.fetch_one = AsyncMock(return_value=None)
        mock_db_manager.execute = AsyncMock()
        
        doc_content = "# 測試文檔\n\n這是一個測試文檔內容。"
        doc_path = documentation_service.api_docs_path / "test_doc.md"
        
        # 執行
        result = await documentation_service._save_document(
            "test_doc", doc_content, doc_path, DocumentCategory.API
        )
        
        # 驗證
        assert result is True
        assert doc_path.exists()
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        assert saved_content == doc_content
        
        # 驗證資料庫調用
        assert mock_db_manager.execute.call_count >= 2
    
    @pytest.mark.unit
    async def test_document_validation_valid_doc(self, documentation_service):
        """測試有效文檔的驗證"""
        # 準備
        await documentation_service._create_directory_structure()
        
        valid_content = """# API 參考文檔

這是一個完整的API文檔，包含詳細的說明和範例。

## 概覽

本文檔提供所有API方法的詳細說明。

## 方法列表

### getUserInfo()

獲取使用者信息的API方法。

```python
user_info = await service.getUserInfo(user_id=12345)
```

這個方法會返回使用者的基本信息。
"""
        
        doc_path = documentation_service.api_docs_path / "valid_doc.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(valid_content)
        
        config = DocumentConfig(
            id="valid_doc",
            category=DocumentCategory.API,
            path=str(doc_path),
            title="Valid Document",
            format=DocumentFormat.MARKDOWN
        )
        documentation_service._document_configs["valid_doc"] = config
        
        # 執行
        result = await documentation_service._validate_single_document("valid_doc")
        
        # 驗證
        assert result is not None
        assert result.is_valid
        assert result.completeness_score > 0.8
        assert result.accuracy_score > 0.7
        assert result.readability_score > 3.0
        assert len(result.issues) == 0
    
    @pytest.mark.unit
    async def test_document_validation_invalid_doc(self, documentation_service):
        """測試無效文檔的驗證"""
        # 準備
        await documentation_service._create_directory_structure()
        
        invalid_content = "太短"
        
        doc_path = documentation_service.api_docs_path / "invalid_doc.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(invalid_content)
        
        config = DocumentConfig(
            id="invalid_doc",
            category=DocumentCategory.API,
            path=str(doc_path),
            title="Invalid Document",
            format=DocumentFormat.MARKDOWN
        )
        documentation_service._document_configs["invalid_doc"] = config
        
        # 執行
        result = await documentation_service._validate_single_document("invalid_doc")
        
        # 驗證
        assert result is not None
        assert not result.is_valid
        assert result.completeness_score < 0.5
        assert len(result.issues) > 0
        assert "文檔內容過短" in result.issues
    
    @pytest.mark.unit
    async def test_completeness_score_calculation(self, documentation_service):
        """測試完整度分數計算"""
        # 測試完整文檔
        complete_content = """# 完整文檔

這是一個完整的文檔範例，包含多個段落和程式碼範例。

## 介紹

詳細的介紹內容，說明這個文檔的目的和用途。

## 使用方法

以下是使用方法的詳細說明：

```python
# 程式碼範例
result = service.method()
```

更多內容說明...

## 參考連結

[相關文檔](https://example.com)
"""
        
        config = DocumentConfig(
            id="test",
            category=DocumentCategory.API,
            path="test.md",
            title="Test",
            format=DocumentFormat.MARKDOWN
        )
        
        score = await documentation_service._calculate_completeness_score(complete_content, config)
        assert score > 0.8
        
        # 測試簡短文檔
        short_content = "# 簡短文檔\n\n這是一個很短的文檔。"
        score = await documentation_service._calculate_completeness_score(short_content, config)
        assert score < 0.8
    
    @pytest.mark.unit
    async def test_readability_score_calculation(self, documentation_service):
        """測試可讀性分數計算"""
        # 測試結構良好的文檔
        readable_content = """# 主標題

這是第一段內容。

## 子標題

這是第二段內容。

### 更小的標題

- 列表項目1
- 列表項目2
- 列表項目3

這是第三段內容。
"""
        
        score = await documentation_service._calculate_readability_score(readable_content)
        assert score > 3.5
        
        # 測試結構簡單的文檔
        simple_content = "這是一個沒有結構的文檔內容。"
        score = await documentation_service._calculate_readability_score(simple_content)
        assert score <= 3.5
    
    @pytest.mark.integration
    async def test_api_docs_generation_integration(self, documentation_service, mock_db_manager):
        """測試API文檔生成整合"""
        # 準備
        await documentation_service._create_directory_structure()
        mock_db_manager.fetch_one = AsyncMock(return_value=None)
        mock_db_manager.execute = AsyncMock()
        
        # 模擬服務類別
        class MockService:
            def get_user(self, user_id: int) -> dict:
                """獲取使用者信息"""
                return {"id": user_id, "name": "test"}
            
            async def create_user(self, name: str, email: str) -> dict:
                """創建新使用者"""
                return {"id": 1, "name": name, "email": email}
        
        # 執行
        with patch.object(documentation_service, '_discover_service_classes', 
                         return_value=[MockService]):
            result = await documentation_service.generate_api_docs()
        
        # 驗證
        assert result is True
        
        api_doc_path = documentation_service.api_docs_path / "api_reference.md"
        assert api_doc_path.exists()
        
        with open(api_doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "# API 參考文檔" in content
        assert "MockService" in content
        assert "get_user" in content
        assert "create_user" in content
    
    @pytest.mark.integration
    async def test_documentation_metrics(self, documentation_service, mock_db_manager):
        """測試文檔指標統計"""
        # 準備
        await documentation_service._create_directory_structure()
        
        # 添加一些模擬文檔配置
        configs = [
            DocumentConfig(
                id="api_doc",
                category=DocumentCategory.API,
                path=str(documentation_service.api_docs_path / "api.md"),
                title="API文檔",
                status=DocumentStatus.PUBLISHED
            ),
            DocumentConfig(
                id="user_doc",
                category=DocumentCategory.USER,
                path=str(documentation_service.user_docs_path / "user.md"),
                title="使用者文檔",
                status=DocumentStatus.DRAFT
            )
        ]
        
        for config in configs:
            documentation_service._document_configs[config.id] = config
            # 創建實際檔案
            Path(config.path).parent.mkdir(parents=True, exist_ok=True)
            with open(config.path, 'w', encoding='utf-8') as f:
                f.write(f"# {config.title}\n\n這是 {config.title} 的內容。")
        
        # 執行
        metrics = await documentation_service.get_documentation_metrics()
        
        # 驗證
        assert metrics.total_documents == 2
        assert metrics.documents_by_category[DocumentCategory.API.value] == 1
        assert metrics.documents_by_category[DocumentCategory.USER.value] == 1
        assert metrics.documents_by_status[DocumentStatus.PUBLISHED.value] == 1
        assert metrics.documents_by_status[DocumentStatus.DRAFT.value] == 1
        assert metrics.total_size_bytes > 0
    
    @pytest.mark.unit
    async def test_permission_validation(self, documentation_service):
        """測試權限驗證"""
        # 測試查看文檔權限（應該允許）
        result = await documentation_service._validate_permissions(12345, 67890, "view_docs")
        assert result is True
        
        # 測試生成文檔權限（應該允許）
        result = await documentation_service._validate_permissions(12345, 67890, "generate_docs")
        assert result is True
        
        # 測試搜尋文檔權限（應該允許）
        result = await documentation_service._validate_permissions(12345, 67890, "search_docs")
        assert result is True
    
    @pytest.mark.unit
    async def test_cleanup(self, documentation_service):
        """測試服務清理"""
        # 準備
        documentation_service._document_configs["test"] = DocumentConfig(
            id="test", category=DocumentCategory.API, path="test.md", title="Test"
        )
        
        # 執行
        await documentation_service._cleanup()
        
        # 驗證
        assert len(documentation_service._document_configs) == 0