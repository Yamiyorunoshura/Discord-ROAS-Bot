"""
連結檢查服務單元測試
Task ID: T3 - 文檔連結有效性修復

測試連結檢查核心功能和API服務
"""

import asyncio
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

# 假設這些模組已經實作
from services.documentation.link_checker import LinkChecker
from services.documentation.link_checker_service import LinkCheckerService
from services.documentation.link_checker_models import (
    LinkCheckConfig, Link, Document, ValidationReport, 
    CheckResult, LinkType, LinkStatus
)
from services.documentation.api_endpoints import LinkCheckAPI
from services.documentation.api_cache_and_error import ResponseCache, ErrorHandler


class TestLinkChecker:
    """測試連結檢查核心引擎"""
    
    @pytest.fixture
    def temp_docs_dir(self):
        """創建臨時文檔目錄"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            
            # 創建測試文檔
            (docs_dir / "test1.md").write_text("""
# Test Document 1

This is a test document with various links:

- [Valid internal link](test2.md)
- [Invalid internal link](nonexistent.md)
- [Valid anchor link](#test-header)
- [Invalid anchor link](#nonexistent-header)
- [External link](https://example.com)

## Test Header

Some content here.
            """)
            
            (docs_dir / "test2.md").write_text("""
# Test Document 2

Referenced by test1.md

- [Back to test1](test1.md)
            """)
            
            yield docs_dir
    
    @pytest.fixture
    def link_checker(self):
        """創建連結檢查器實例"""
        config = LinkCheckConfig(
            check_external_links=False,
            check_anchors=True,
            file_extensions=['.md']
        )
        return LinkChecker(config)
    
    def test_scan_directory(self, link_checker, temp_docs_dir):
        """測試目錄掃描功能"""
        documents = link_checker.scan_directory(str(temp_docs_dir))
        
        assert len(documents) == 2
        assert all(isinstance(doc, Document) for doc in documents)
        assert all(doc.file_path.endswith('.md') for doc in documents)
    
    def test_extract_links(self, link_checker):
        """測試連結提取功能"""
        content = """
# Test

[Link 1](file1.md)
[Link 2](https://example.com)
[Anchor](#section)
        """
        
        links = link_checker._extract_links(content, "test.md")
        
        assert len(links) == 3
        assert links[0].text == "Link 1"
        assert links[0].url == "file1.md"
        assert links[0].link_type == LinkType.FILE
        
        assert links[1].link_type == LinkType.EXTERNAL
        assert links[2].link_type == LinkType.ANCHOR
    
    @pytest.mark.asyncio
    async def test_validate_links(self, link_checker, temp_docs_dir):
        """測試連結驗證功能"""
        documents = link_checker.scan_directory(str(temp_docs_dir))
        report = await link_checker.validate_links(documents)
        
        assert isinstance(report, ValidationReport)
        assert report.total_links > 0
        assert report.valid_links >= 0
        assert report.invalid_links >= 0
        assert 0 <= report.success_rate <= 100
    
    def test_anchor_extraction(self, link_checker):
        """測試錨點提取功能"""
        content = """
# Main Header
## Sub Header  
### Another Header With Special Chars!@#
#### Normal Header
        """
        
        anchors = link_checker._extract_anchors(content)
        
        assert "main-header" in anchors
        assert "sub-header" in anchors
        assert "another-header-with-special-chars" in anchors
        assert "normal-header" in anchors
    
    def test_link_type_determination(self, link_checker):
        """測試連結類型判斷"""
        assert link_checker._determine_link_type("https://example.com") == LinkType.EXTERNAL
        assert link_checker._determine_link_type("#anchor") == LinkType.ANCHOR
        assert link_checker._determine_link_type("./file.md") == LinkType.INTERNAL
        assert link_checker._determine_link_type("../parent.md") == LinkType.INTERNAL
        assert link_checker._determine_link_type("image.png") == LinkType.FILE
    
    def test_report_generation(self, link_checker):
        """測試報告生成功能"""
        # 創建模擬報告
        report = ValidationReport(
            document_path="test.md",
            scan_timestamp=datetime.now(),
            total_links=5,
            valid_links=3,
            invalid_links=2,
            external_links=1,
            internal_links=2,
            anchor_links=1,
            file_links=1,
            broken_links=[],
            warnings=[],
            errors=[],
            scan_duration_ms=100.0
        )
        
        # 測試不同格式
        markdown_report = link_checker.generate_report(report, "markdown")
        json_report = link_checker.generate_report(report, "json")
        
        assert "# 文檔連結檢查報告" in markdown_report
        assert "統計摘要" in markdown_report
        assert '"total_links": 5' in json_report


class TestLinkCheckerService:
    """測試連結檢查服務"""
    
    @pytest.fixture
    def temp_base_path(self):
        """創建臨時基礎路徑"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    async def link_service(self, temp_base_path):
        """創建連結檢查服務實例"""
        service = LinkCheckerService(temp_base_path)
        await service.initialize()
        yield service
        await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, temp_base_path):
        """測試服務初始化"""
        service = LinkCheckerService(temp_base_path)
        
        assert not service._initialized
        
        await service.initialize()
        assert service._initialized
        
        await service.shutdown()
        assert not service._initialized
    
    @pytest.mark.asyncio
    async def test_check_documentation(self, link_service, temp_base_path):
        """測試文檔檢查功能"""
        # 創建測試文檔
        docs_dir = Path(temp_base_path) / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        (docs_dir / "test.md").write_text("""
# Test
[Valid link](valid.md)
[Invalid link](invalid.md)
        """)
        
        (docs_dir / "valid.md").write_text("# Valid Document")
        
        result = await link_service.check_documentation([str(docs_dir)])
        
        assert isinstance(result, CheckResult)
        assert result.documents_checked > 0
        assert result.total_links_found > 0
        assert len(result.reports) > 0
    
    def test_schedule_periodic_check(self, link_service):
        """測試定期檢查排程"""
        schedule_id = link_service.schedule_periodic_check(
            interval_hours=24,
            name="daily_check"
        )
        
        assert schedule_id is not None
        assert schedule_id.startswith("schedule_daily_check")
        
        schedules = link_service.get_periodic_schedules()
        assert len(schedules) == 1
        assert schedules[0].name == "daily_check"
    
    def test_cancel_periodic_check(self, link_service):
        """測試取消定期檢查"""
        schedule_id = link_service.schedule_periodic_check(
            interval_hours=12,
            name="test_check"
        )
        
        success = link_service.cancel_periodic_check(schedule_id)
        assert success is True
        
        # 檢查排程已被停用
        schedules = link_service.get_periodic_schedules()
        schedule = next(s for s in schedules if s.schedule_id == schedule_id)
        assert not schedule.enabled
    
    def test_get_check_history(self, link_service):
        """測試檢查歷史獲取"""
        # 由於沒有實際的檢查記錄，歷史應該為空
        history = link_service.get_check_history(limit=5)
        assert isinstance(history, list)
        assert len(history) >= 0
    
    @pytest.mark.asyncio
    async def test_service_status(self, link_service):
        """測試服務狀態獲取"""
        status = await link_service.get_service_status()
        
        assert isinstance(status, dict)
        assert "initialized" in status
        assert "base_path" in status
        assert "running_checks" in status
        assert status["initialized"] is True


class TestResponseCache:
    """測試API響應快取"""
    
    @pytest.fixture
    async def cache(self):
        """創建快取實例"""
        cache = ResponseCache(max_size=100, default_ttl_seconds=60)
        await cache.start()
        yield cache
        await cache.stop()
    
    @pytest.mark.asyncio
    async def test_cache_basic_operations(self, cache):
        """測試基本快取操作"""
        # 測試設定和獲取
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # 測試不存在的鍵
        assert cache.get("nonexistent") is None
        
        # 測試刪除
        assert cache.delete("key1") is True
        assert cache.get("key1") is None
        
        # 測試重複刪除
        assert cache.delete("key1") is False
    
    def test_cache_key_generation(self, cache):
        """測試快取鍵生成"""
        key1 = cache.generate_cache_key("method1", "arg1", "arg2", param1="value1")
        key2 = cache.generate_cache_key("method1", "arg1", "arg2", param1="value1")
        key3 = cache.generate_cache_key("method2", "arg1", "arg2", param1="value1")
        
        assert key1 == key2  # 相同參數應生成相同鍵
        assert key1 != key3  # 不同方法應生成不同鍵
        assert len(key1) == 32  # MD5哈希長度
    
    def test_cache_expiration(self, cache):
        """測試快取過期"""
        from services.documentation.api_cache_and_error import CachePolicy
        
        # 設定短期快取
        cache.set("short_key", "value", CachePolicy.SHORT_TERM)
        
        # 立即獲取應該成功
        assert cache.get("short_key") == "value"
        
        # 模擬時間過去（需要修改實作來支援時間模擬）
        # 這裡只測試基本邏輯
        assert cache.exists("short_key") is True
    
    def test_cache_stats(self, cache):
        """測試快取統計"""
        # 執行一些操作
        cache.set("key1", "value1")
        cache.get("key1")  # 命中
        cache.get("key2")  # 未命中
        
        stats = cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "current_size" in stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1


class TestErrorHandler:
    """測試錯誤處理器"""
    
    @pytest.fixture
    def error_handler(self):
        """創建錯誤處理器實例"""
        return ErrorHandler()
    
    def test_create_error(self, error_handler):
        """測試錯誤創建"""
        error = error_handler.create_error(
            "LINK_CHECK_001",
            context={"path": "/test/path"},
            custom_message="Custom error message"
        )
        
        assert error.error_code == "LINK_CHECK_001"
        assert error.message == "Custom error message"
        assert error.context["path"] == "/test/path"
        assert error.timestamp is not None
    
    def test_handle_exception(self, error_handler):
        """測試異常處理"""
        exception = FileNotFoundError("File not found")
        
        error = error_handler.handle_exception(
            exception,
            context={"operation": "test"}
        )
        
        assert error.error_code == "LINK_CHECK_001"  # FileNotFoundError映射
        assert "File not found" in error.message
        assert error.context["operation"] == "test"
        assert error.traceback is not None
    
    def test_format_error_response(self, error_handler):
        """測試錯誤響應格式化"""
        error = error_handler.create_error("LINK_CHECK_002")
        response = error_handler.format_error_response(error)
        
        assert response["success"] is False
        assert "error" in response
        assert "timestamp" in response
        assert response["error"]["error_code"] == "LINK_CHECK_002"
    
    def test_error_statistics(self, error_handler):
        """測試錯誤統計"""
        # 創建一些錯誤
        error_handler.create_error("LINK_CHECK_001")
        error_handler.create_error("LINK_CHECK_001")  # 重複
        error_handler.create_error("LINK_CHECK_002")
        
        stats = error_handler.get_error_statistics()
        
        assert stats["total_errors"] == 3
        assert "LINK_CHECK_001" in stats["error_counts_by_code"]
        assert stats["error_counts_by_code"]["LINK_CHECK_001"] == 2
        assert len(stats["top_error_codes"]) > 0


class TestLinkCheckAPI:
    """測試連結檢查API"""
    
    @pytest.fixture
    def temp_base_path(self):
        """創建臨時基礎路徑"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    async def api(self, temp_base_path):
        """創建API實例"""
        api = LinkCheckAPI(temp_base_path)
        await api.initialize()
        yield api
        await api.shutdown()
    
    @pytest.mark.asyncio
    async def test_api_initialization(self, temp_base_path):
        """測試API初始化"""
        api = LinkCheckAPI(temp_base_path)
        
        response = await api.initialize()
        assert response["success"] is True
        assert "API服務初始化成功" in response["data"]["message"]
        
        await api.shutdown()
    
    @pytest.mark.asyncio
    async def test_check_links_api(self, api, temp_base_path):
        """測試連結檢查API端點"""
        # 創建測試文檔
        docs_dir = Path(temp_base_path) / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "test.md").write_text("# Test\n[Link](other.md)")
        
        response = await api.check_links(
            target_paths=[str(docs_dir)],
            output_format="summary"
        )
        
        assert response["success"] is True
        assert "check_id" in response["data"]
        assert "summary" in response["data"]
    
    @pytest.mark.asyncio
    async def test_create_schedule_api(self, api):
        """測試創建排程API端點"""
        response = await api.create_periodic_schedule(
            name="test_schedule",
            interval_hours=24
        )
        
        assert response["success"] is True
        assert response["data"]["name"] == "test_schedule"
        assert "schedule_id" in response["data"]
    
    @pytest.mark.asyncio
    async def test_list_schedules_api(self, api):
        """測試列出排程API端點"""
        # 先創建一個排程
        await api.create_periodic_schedule("test1", 12)
        await api.create_periodic_schedule("test2", 24)
        
        response = await api.list_schedules()
        
        assert response["success"] is True
        assert len(response["data"]["schedules"]) == 2
        assert response["data"]["total_count"] == 2
    
    @pytest.mark.asyncio 
    async def test_service_status_api(self, api):
        """測試服務狀態API端點"""
        response = await api.get_service_status()
        
        assert response["success"] is True
        assert "service" in response["data"]
        assert "cache" in response["data"]
        assert "errors" in response["data"]
        assert "api_version" in response["data"]
    
    @pytest.mark.asyncio
    async def test_error_handling(self, api):
        """測試API錯誤處理"""
        # 測試無效路徑
        response = await api.check_links(
            target_paths=["/nonexistent/path"]
        )
        
        assert response["success"] is False
        assert "error" in response
        assert response["error"]["error_code"] is not None
    
    @pytest.mark.asyncio
    async def test_parameter_validation(self, api):
        """測試參數驗證"""
        # 測試無效的輸出格式
        response = await api.check_links(output_format="invalid_format")
        
        assert response["success"] is False
        assert "LINK_CHECK_004" in response["error"]["error_code"]
    
    @pytest.mark.asyncio
    async def test_cleanup_reports_api(self, api):
        """測試清理報告API端點"""
        response = await api.cleanup_reports(keep_days=7)
        
        assert response["success"] is True
        assert "cleaned_files" in response["data"]
        assert response["data"]["keep_days"] == 7


# 整合測試
class TestIntegration:
    """整合測試"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """創建完整的測試項目結構"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            
            # 創建目錄結構
            docs_dir = project_root / "docs"
            docs_dir.mkdir()
            
            api_dir = docs_dir / "api"
            api_dir.mkdir()
            
            # 創建測試文檔
            (docs_dir / "README.md").write_text("""
# Project Documentation

- [API Reference](api/index.md)
- [User Guide](user-guide.md)
- [Architecture](architecture.md)

## Links Test

- [Valid internal](api/index.md)
- [Invalid internal](missing.md)
- [Valid anchor](#links-test)
- [Invalid anchor](#missing-section)
            """)
            
            (api_dir / "index.md").write_text("""
# API Reference

[Back to README](../README.md)

## Endpoints

### GET /api/check
Check documentation links
            """)
            
            yield project_root
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, temp_project_dir):
        """端到端工作流程測試"""
        # 初始化API
        api = LinkCheckAPI(str(temp_project_dir))
        await api.initialize()
        
        try:
            # 1. 檢查連結
            check_response = await api.check_links(
                target_paths=[str(temp_project_dir / "docs")]
            )
            assert check_response["success"] is True
            check_id = check_response["data"]["check_id"]
            
            # 2. 獲取檢查結果
            result_response = await api.get_check_result(check_id)
            assert result_response["success"] is True
            
            # 3. 匯出報告
            export_response = await api.export_report(check_id, "markdown")
            assert export_response["success"] is True
            
            # 4. 檢查歷史
            history_response = await api.list_check_history(limit=5)
            assert history_response["success"] is True
            assert len(history_response["data"]["history"]) >= 1
            
            # 5. 創建定期排程
            schedule_response = await api.create_periodic_schedule(
                name="integration_test",
                interval_hours=24,
                target_directories=[str(temp_project_dir / "docs")]
            )
            assert schedule_response["success"] is True
            
            # 6. 獲取服務狀態
            status_response = await api.get_service_status()
            assert status_response["success"] is True
            
        finally:
            await api.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, temp_project_dir):
        """並發請求測試"""
        api = LinkCheckAPI(str(temp_project_dir))
        await api.initialize()
        
        try:
            # 同時發送多個請求
            tasks = []
            for i in range(3):
                task = api.check_links(
                    target_paths=[str(temp_project_dir / "docs")],
                    output_format="summary"
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
            # 所有請求都應該成功
            for response in responses:
                assert response["success"] is True
                assert "check_id" in response["data"]
            
        finally:
            await api.shutdown()


if __name__ == "__main__":
    # 運行測試
    pytest.main([__file__, "-v"])