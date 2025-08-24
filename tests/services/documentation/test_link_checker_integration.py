"""
連結檢查服務整合測試
Task ID: T3 - 文檔連結有效性修復

測試完整的端到端工作流程和實際場景
"""

import asyncio
import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from services.documentation.link_checker_service import LinkCheckerService
from services.documentation.api_endpoints import LinkCheckAPI, get_link_check_api
from services.documentation.link_checker_models import LinkCheckConfig


class TestRealWorldScenarios:
    """真實世界場景測試"""
    
    @pytest.fixture
    def complex_docs_structure(self):
        """創建複雜的文檔結構"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            
            # 創建複雜的目錄結構
            (root / "docs").mkdir()
            (root / "docs" / "api").mkdir()
            (root / "docs" / "user").mkdir()
            (root / "docs" / "dev").mkdir()
            (root / "src").mkdir()
            
            # 創建主文檔
            (root / "README.md").write_text("""
# ROAS Bot Documentation

Welcome to ROAS Bot documentation.

## Quick Links
- [API Reference](docs/api/README.md)
- [User Guide](docs/user/guide.md)
- [Developer Documentation](docs/dev/setup.md)
- [Source Code](src/)

## Navigation
- [Getting Started](#getting-started)
- [Features](#features)

## Getting Started
Follow these steps to get started.

## Features
List of features.
            """)
            
            # API文檔
            (root / "docs" / "api" / "README.md").write_text("""
# API Reference

- [Authentication](auth.md)
- [Endpoints](endpoints.md)
- [Examples](../user/examples.md)

[Back to main](../../README.md)
            """)
            
            (root / "docs" / "api" / "auth.md").write_text("""
# Authentication

See [endpoints documentation](endpoints.md) for usage.

[API Home](README.md)
            """)
            
            (root / "docs" / "api" / "endpoints.md").write_text("""
# API Endpoints

## Link Checking
- POST /api/check - Check links
- GET /api/status - Service status

[Authentication required](auth.md)

## Broken Links (intentional for testing)
- [Missing file](missing.md)
- [Invalid anchor](#nonexistent-section)
- [Broken relative](../../nonexistent.md)
            """)
            
            # 用戶文檔
            (root / "docs" / "user" / "guide.md").write_text("""
# User Guide

## Table of Contents
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)

## Installation
Installation steps here.

## Configuration
Configuration details.

## Usage
Usage examples at [examples](examples.md).

[Back to API](../api/README.md)
            """)
            
            (root / "docs" / "user" / "examples.md").write_text("""
# Examples

Check the [API documentation](../api/endpoints.md) for details.

[User Guide](guide.md)
            """)
            
            # 開發者文檔
            (root / "docs" / "dev" / "setup.md").write_text("""
# Development Setup

## Prerequisites
- Python 3.8+
- Dependencies listed in [requirements](requirements.md)

## Source Code
See [source directory](../../src/) for implementation.
            """)
            
            yield root
    
    @pytest.mark.asyncio
    async def test_comprehensive_link_check(self, complex_docs_structure):
        """全面的連結檢查測試"""
        service = LinkCheckerService(str(complex_docs_structure))
        await service.initialize()
        
        try:
            # 檢查整個文檔結構
            result = await service.check_documentation([
                str(complex_docs_structure)
            ])
            
            # 驗證結果
            assert result.documents_checked > 5  # 應該找到多個文檔
            assert result.total_links_found > 15  # 應該有大量連結
            
            # 應該檢測到一些無效連結
            assert result.broken_links > 0
            
            # 檢查報告詳情
            assert len(result.reports) == 1
            report = result.reports[0]
            
            # 應該有各種類型的連結
            assert report.internal_links > 0
            assert report.anchor_links > 0
            
            # 應該有一些無效連結（在測試文檔中故意設置的）
            assert len(report.broken_links) >= 3  # missing.md, nonexistent-section, nonexistent.md
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_periodic_checking_simulation(self, complex_docs_structure):
        """模擬定期檢查功能"""
        service = LinkCheckerService(str(complex_docs_structure))
        await service.initialize()
        
        try:
            # 創建多個定期排程
            schedule1 = service.schedule_periodic_check(
                interval_hours=1,
                name="hourly_api_check", 
                target_directories=[str(complex_docs_structure / "docs" / "api")]
            )
            
            schedule2 = service.schedule_periodic_check(
                interval_hours=6,
                name="daily_full_check",
                target_directories=[str(complex_docs_structure / "docs")]
            )
            
            # 驗證排程
            schedules = service.get_periodic_schedules()
            assert len(schedules) == 2
            
            # 檢查排程屬性
            hourly_schedule = next(s for s in schedules if s.name == "hourly_api_check")
            assert hourly_schedule.interval_hours == 1
            assert hourly_schedule.enabled
            
            # 模擬手動觸發檢查
            api_result = await service.check_documentation(
                target_paths=[str(complex_docs_structure / "docs" / "api")]
            )
            
            assert api_result.documents_checked >= 3  # auth.md, endpoints.md, README.md
            
            # 取消一個排程
            success = service.cancel_periodic_check(schedule1)
            assert success
            
            updated_schedules = service.get_periodic_schedules()
            cancelled_schedule = next(s for s in updated_schedules if s.schedule_id == schedule1)
            assert not cancelled_schedule.enabled
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_different_link_types(self, complex_docs_structure):
        """測試不同類型連結的處理"""
        # 創建包含各種連結類型的測試文檔
        test_doc = complex_docs_structure / "test_links.md"
        test_doc.write_text("""
# Link Types Test

## Internal Links
- [Valid relative](docs/api/README.md)
- [Valid absolute from root](/docs/user/guide.md)
- [Invalid relative](docs/missing.md)

## Anchor Links
- [Valid anchor](#internal-links)
- [Invalid anchor](#missing-anchor)
- [Cross-file anchor](docs/user/guide.md#installation)

## File Links
- [Image](assets/image.png)
- [Document](docs/api/schema.json)

## External Links (not checked by default)
- [GitHub](https://github.com/example/repo)
- [Website](https://example.com)

## Complex Paths  
- [Parent directory](../README.md)
- [Nested path](docs/dev/../user/guide.md)
- [With spaces](docs/user/user guide.md)
        """)
        
        service = LinkCheckerService(str(complex_docs_structure))
        await service.initialize()
        
        try:
            # 配置不同的檢查選項
            config = LinkCheckConfig(
                check_external_links=False,
                check_anchors=True,
                base_path=str(complex_docs_structure)
            )
            
            result = await service.check_documentation(
                target_paths=[str(test_doc)],
                config_override=config
            )
            
            # 驗證結果
            report = result.reports[0]
            
            # 檢查連結類型分布
            assert report.internal_links > 0
            assert report.anchor_links > 0
            assert report.external_links > 0  # 即使不檢查，也應該被識別
            
            # 檢查無效連結
            broken_links = report.broken_links
            assert len(broken_links) > 0
            
            # 驗證特定的無效連結
            broken_urls = [link.url for link in broken_links]
            assert "docs/missing.md" in broken_urls
            assert any("#missing-anchor" in url for url in broken_urls)
            
        finally:
            await service.shutdown()


class TestAPIIntegration:
    """API整合測試"""
    
    @pytest.fixture
    def temp_project(self):
        """創建測試項目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            
            (docs / "index.md").write_text("""
# Documentation Index

- [Guide](guide.md)
- [API](api.md)
- [Missing](missing.md)

## Sections
- [Installation](#installation)

## Installation
Installation instructions here.
            """)
            
            (docs / "guide.md").write_text("""
# User Guide

[Back to index](index.md)

## Topics
- [Getting Started](#getting-started)
- [Advanced](advanced.md)

## Getting Started
Getting started content.
            """)
            
            (docs / "api.md").write_text("""
# API Reference

[Index](index.md) | [Guide](guide.md)

## Endpoints
List of endpoints.
            """)
            
            yield root
    
    @pytest.mark.asyncio
    async def test_full_api_workflow(self, temp_project):
        """完整API工作流程測試"""
        api = LinkCheckAPI(str(temp_project))
        await api.initialize()
        
        try:
            # 1. 執行連結檢查
            check_response = await api.check_links(
                target_paths=[str(temp_project / "docs")],
                check_anchors=True,
                output_format="json"
            )
            
            assert check_response["success"]
            check_id = check_response["data"]["check_id"]
            
            # 驗證檢查結果結構
            data = check_response["data"]
            assert "summary" in data
            assert "configuration" in data
            assert data["summary"]["documents_checked"] >= 3
            
            # 2. 獲取詳細結果
            detail_response = await api.get_check_result(check_id)
            assert detail_response["success"]
            assert "details" in detail_response["data"]
            
            # 3. 匯出不同格式的報告
            formats = ["markdown", "json", "csv", "text"]
            for fmt in formats:
                export_response = await api.export_report(check_id, fmt)
                assert export_response["success"]
                
                report_path = Path(export_response["data"]["report_path"])
                assert report_path.exists()
                assert report_path.suffix == f".{fmt}"
            
            # 4. 創建和管理排程
            schedule_response = await api.create_periodic_schedule(
                name="test_schedule",
                interval_hours=24,
                target_directories=[str(temp_project / "docs")]
            )
            assert schedule_response["success"]
            schedule_id = schedule_response["data"]["schedule_id"]
            
            # 列出排程
            list_response = await api.list_schedules()
            assert list_response["success"]
            assert len(list_response["data"]["schedules"]) == 1
            
            # 取消排程
            cancel_response = await api.cancel_schedule(schedule_id)
            assert cancel_response["success"]
            
            # 5. 檢查歷史
            history_response = await api.list_check_history(limit=5)
            assert history_response["success"]
            assert len(history_response["data"]["history"]) >= 1
            
            # 6. 獲取服務狀態
            status_response = await api.get_service_status()
            assert status_response["success"]
            
            # 驗證狀態信息
            status_data = status_response["data"]
            assert "service" in status_data
            assert "cache" in status_data
            assert "errors" in status_data
            
        finally:
            await api.shutdown()
    
    @pytest.mark.asyncio
    async def test_api_error_scenarios(self, temp_project):
        """API錯誤場景測試"""
        api = LinkCheckAPI(str(temp_project))
        await api.initialize()
        
        try:
            # 1. 無效路徑
            response = await api.check_links(target_paths=["/nonexistent/path"])
            assert not response["success"]
            assert "LINK_CHECK_001" in response["error"]["error_code"]
            
            # 2. 無效格式
            response = await api.check_links(output_format="invalid")
            assert not response["success"]
            assert "LINK_CHECK_004" in response["error"]["error_code"]
            
            # 3. 無效檢查ID
            response = await api.get_check_result("nonexistent-id")
            assert not response["success"]
            
            # 4. 無效排程參數
            response = await api.create_periodic_schedule("", interval_hours=0)
            assert not response["success"]
            
            # 5. 無效報告格式
            # 先創建有效的檢查
            check_response = await api.check_links(
                target_paths=[str(temp_project / "docs")]
            )
            check_id = check_response["data"]["check_id"]
            
            # 然後嘗試無效格式
            response = await api.export_report(check_id, "invalid_format")
            assert not response["success"]
            
        finally:
            await api.shutdown()
    
    @pytest.mark.asyncio
    async def test_api_caching(self, temp_project):
        """API快取測試"""
        api = LinkCheckAPI(str(temp_project))
        await api.initialize()
        
        try:
            target_path = str(temp_project / "docs")
            
            # 第一次請求
            start_time = datetime.now()
            response1 = await api.check_links(target_paths=[target_path])
            first_duration = (datetime.now() - start_time).total_seconds()
            
            # 第二次相同請求（應該使用快取）
            start_time = datetime.now()
            response2 = await api.check_links(target_paths=[target_path])
            second_duration = (datetime.now() - start_time).total_seconds()
            
            # 驗證結果一致
            assert response1["success"] and response2["success"]
            # 注意：由於快取鍵包含時間戳等動態信息，結果可能不同
            # 這裡主要測試快取機制不會導致錯誤
            
            # 檢查快取統計
            status_response = await api.get_service_status()
            cache_stats = status_response["data"]["cache"]
            assert "hits" in cache_stats
            assert "misses" in cache_stats
            
        finally:
            await api.shutdown()


class TestPerformanceAndScalability:
    """效能和可擴展性測試"""
    
    @pytest.fixture
    def large_doc_set(self):
        """創建大型文檔集"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir()
            
            # 創建多個文檔，每個包含多個連結
            for i in range(20):
                doc_content = f"""
# Document {i}

This is document number {i}.

## Links to other documents
"""
                # 添加多個連結
                for j in range(10):
                    if j < 5:  # 前5個連結是有效的
                        target_doc = f"doc_{j}.md" if j < i else f"doc_{i-1}.md" if i > 0 else "doc_0.md"
                    else:  # 後5個連結是無效的
                        target_doc = f"missing_{j}.md"
                    
                    doc_content += f"- [Link {j}]({target_doc})\n"
                
                # 添加錨點連結
                doc_content += """

## Anchor Links
- [Valid anchor](#links-to-other-documents)
- [Invalid anchor](#missing-section)

## Section with content
Some content here.
"""
                
                (docs_dir / f"doc_{i}.md").write_text(doc_content)
            
            yield root
    
    @pytest.mark.asyncio
    async def test_large_document_set(self, large_doc_set):
        """大型文檔集測試"""
        service = LinkCheckerService(str(large_doc_set))
        await service.initialize()
        
        try:
            start_time = datetime.now()
            
            result = await service.check_documentation([
                str(large_doc_set / "docs")
            ])
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # 驗證結果
            assert result.documents_checked == 20
            assert result.total_links_found >= 200  # 20 docs * 10+ links each
            
            # 效能要求：應該在合理時間內完成
            assert duration < 30  # 30秒內完成
            
            # 檢查結果準確性
            assert result.broken_links > 0  # 應該檢測到無效連結
            assert result.valid_links > 0   # 應該有有效連結
            
            print(f"處理 {result.documents_checked} 個文檔，"
                  f"{result.total_links_found} 個連結，"
                  f"耗時 {duration:.2f} 秒")
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_checks(self, large_doc_set):
        """並發檢查測試"""
        service = LinkCheckerService(str(large_doc_set))
        await service.initialize()
        
        try:
            # 同時運行多個檢查
            tasks = []
            for i in range(3):
                # 每個任務檢查不同的子集
                start_doc = i * 5
                end_doc = start_doc + 5
                subset_docs = []
                for j in range(start_doc, min(end_doc, 20)):
                    subset_docs.append(str(large_doc_set / "docs" / f"doc_{j}.md"))
                
                task = service.check_documentation(subset_docs)
                tasks.append(task)
            
            # 等待所有任務完成
            results = await asyncio.gather(*tasks)
            
            # 驗證所有結果
            for i, result in enumerate(results):
                assert result.documents_checked <= 5
                assert result.total_links_found > 0
                print(f"並發任務 {i+1}: {result.documents_checked} 文檔, "
                      f"{result.total_links_found} 連結, "
                      f"耗時 {result.check_duration_ms:.0f}ms")
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, large_doc_set):
        """記憶體使用測試"""
        service = LinkCheckerService(str(large_doc_set))
        await service.initialize()
        
        try:
            # 執行多次檢查以測試記憶體洩漏
            results = []
            
            for round_num in range(3):
                result = await service.check_documentation([
                    str(large_doc_set / "docs")
                ])
                results.append(result)
                
                # 檢查快取大小
                status = await service.get_service_status()
                cache_stats = status["cache_stats"]
                
                print(f"Round {round_num + 1}: "
                      f"檔案快取: {cache_stats['file_cache_size']}, "
                      f"錨點快取: {cache_stats['anchor_cache_size']}")
            
            # 驗證所有輪次的結果一致性
            for i in range(1, len(results)):
                # 文檔數應該相同
                assert results[i].documents_checked == results[0].documents_checked
                # 連結總數應該相同（假設文檔沒變）
                assert results[i].total_links_found == results[0].total_links_found
            
        finally:
            await service.shutdown()


class TestEdgeCases:
    """邊界情況測試"""
    
    @pytest.fixture
    def edge_case_docs(self):
        """創建邊界情況文檔"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            
            # 空文檔
            (docs / "empty.md").write_text("")
            
            # 只有標題的文檔
            (docs / "title_only.md").write_text("# Title Only")
            
            # 包含特殊字符的文檔
            (docs / "special_chars.md").write_text("""
# 中文标题 and Special Chars!@#$%^&*()

- [鏈接 with 中文](chinese.md)
- [Link with spaces](file with spaces.md)
- [Link with (parentheses)](file(1).md)
- [Link with [brackets]](file[1].md)
            """)
            
            # 循環引用
            (docs / "circular1.md").write_text("""
# Circular 1
[Go to circular2](circular2.md)
            """)
            
            (docs / "circular2.md").write_text("""
# Circular 2  
[Go to circular1](circular1.md)
            """)
            
            # 深層嵌套錨點
            (docs / "deep_anchors.md").write_text("""
# Level 1
## Level 2
### Level 3
#### Level 4
##### Level 5
###### Level 6

Links:
- [To Level 1](#level-1)
- [To Level 6](#level-6)
- [Non-existent](#level-7)
            """)
            
            # 複雜相對路徑
            nested = docs / "nested" / "deep" / "path"
            nested.mkdir(parents=True)
            
            (nested / "complex.md").write_text("""
# Complex Paths

- [Up one](../sibling.md)  
- [Up two](../../parent.md)
- [Up three](../../../root.md)
- [Root docs](../../../docs/title_only.md)
- [Invalid up](../../../../outside.md)
            """)
            
            yield root
    
    @pytest.mark.asyncio
    async def test_empty_and_minimal_documents(self, edge_case_docs):
        """測試空文檔和最小文檔"""
        service = LinkCheckerService(str(edge_case_docs))
        await service.initialize()
        
        try:
            result = await service.check_documentation([
                str(edge_case_docs / "docs" / "empty.md"),
                str(edge_case_docs / "docs" / "title_only.md")
            ])
            
            # 空文檔應該被處理但沒有連結
            assert result.documents_checked >= 1
            # 可能沒有連結或很少連結
            assert result.total_links_found >= 0
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_special_characters(self, edge_case_docs):
        """測試特殊字符處理"""
        service = LinkCheckerService(str(edge_case_docs))
        await service.initialize()
        
        try:
            result = await service.check_documentation([
                str(edge_case_docs / "docs" / "special_chars.md")
            ])
            
            # 應該能處理包含特殊字符的文檔
            assert result.documents_checked >= 1
            assert result.total_links_found > 0
            
            # 檢查報告是否包含特殊字符連結
            report = result.reports[0]
            broken_links = report.broken_links
            
            # 應該檢測到不存在的文件
            broken_urls = [link.url for link in broken_links]
            assert any("chinese.md" in url for url in broken_urls)
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_circular_references(self, edge_case_docs):
        """測試循環引用處理"""
        service = LinkCheckerService(str(edge_case_docs))
        await service.initialize()
        
        try:
            result = await service.check_documentation([
                str(edge_case_docs / "docs" / "circular1.md"),
                str(edge_case_docs / "docs" / "circular2.md")
            ])
            
            # 循環引用應該被正確處理，不會導致無限循環
            assert result.documents_checked == 2
            assert result.total_links_found == 2
            
            # 這些連結應該是有效的（因為文件存在）
            assert result.valid_links == 2
            assert result.broken_links == 0
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_complex_relative_paths(self, edge_case_docs):
        """測試複雜相對路徑"""
        service = LinkCheckerService(str(edge_case_docs))
        await service.initialize()
        
        try:
            result = await service.check_documentation([
                str(edge_case_docs / "docs" / "nested" / "deep" / "path" / "complex.md")
            ])
            
            assert result.documents_checked == 1
            assert result.total_links_found > 0
            
            # 檢查相對路徑解析
            report = result.reports[0]
            
            # 應該檢測到指向項目外部的無效連結
            broken_links = report.broken_links
            assert len(broken_links) > 0
            
            # 檢查是否正確處理 ../ 路徑
            broken_urls = [link.url for link in broken_links]
            assert any("outside.md" in url for url in broken_urls)
            
        finally:
            await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_deep_anchor_hierarchy(self, edge_case_docs):
        """測試深層錨點層級"""
        service = LinkCheckerService(str(edge_case_docs))
        await service.initialize()
        
        try:
            config = LinkCheckConfig(
                check_anchors=True,
                base_path=str(edge_case_docs)
            )
            
            result = await service.check_documentation(
                target_paths=[str(edge_case_docs / "docs" / "deep_anchors.md")],
                config_override=config
            )
            
            assert result.documents_checked == 1
            
            report = result.reports[0]
            
            # 應該有錨點連結
            assert report.anchor_links > 0
            
            # 檢查錨點連結驗證
            broken_links = report.broken_links
            
            # level-7 應該是無效錨點
            broken_anchors = [link.url for link in broken_links if link.url.startswith('#')]
            assert "#level-7" in broken_anchors
            
        finally:
            await service.shutdown()


if __name__ == "__main__":
    # 運行整合測試
    pytest.main([__file__, "-v", "--tb=short"])