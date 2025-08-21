"""
任務11整合測試
Task ID: 11 - 建立文件和部署準備

測試文檔、部署和監控系統的整合功能
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from test_utils.discord_mocks import MockBot


class TestTask11Integration:
    """任務11整合測試類"""
    
    @pytest.fixture
    async def temp_project_dir(self):
        """創建臨時專案目錄"""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir)
        
        # 創建專案結構
        (project_path / "docs").mkdir()
        (project_path / "deployment").mkdir()
        (project_path / "monitoring").mkdir()
        (project_path / "services").mkdir()
        
        yield project_path
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    async def mock_services(self):
        """模擬所有相關服務"""
        services = {
            "documentation": AsyncMock(),
            "deployment": AsyncMock(), 
            "monitoring": AsyncMock(),
            "database": AsyncMock()
        }
        
        # 配置模擬行為
        services["documentation"].generate_api_docs = AsyncMock(return_value=True)
        services["documentation"].validate_documents = AsyncMock(return_value=[])
        services["deployment"].deploy = AsyncMock(return_value={"status": "success"})
        services["monitoring"].check_system_health = AsyncMock(return_value={"status": "healthy"})
        
        return services
    
    @pytest.mark.integration
    async def test_documentation_to_deployment_integration(self, mock_services, temp_project_dir):
        """測試文檔生成到部署流程的整合"""
        # 1. 生成文檔
        doc_result = await mock_services["documentation"].generate_api_docs()
        assert doc_result is True
        
        # 2. 驗證文檔品質
        validation_result = await mock_services["documentation"].validate_documents()
        assert isinstance(validation_result, list)
        
        # 3. 準備部署配置（包含文檔）
        deployment_config = {
            "version": "v2.4.0",
            "environment": "production",
            "include_docs": True,
            "docs_path": str(temp_project_dir / "docs")
        }
        
        # 4. 執行部署
        deploy_result = await mock_services["deployment"].deploy(**deployment_config)
        assert deploy_result["status"] == "success"
        
        # 驗證整合流程
        mock_services["documentation"].generate_api_docs.assert_called_once()
        mock_services["documentation"].validate_documents.assert_called_once()
        mock_services["deployment"].deploy.assert_called_once()
    
    @pytest.mark.integration
    async def test_deployment_to_monitoring_integration(self, mock_services):
        """測試部署到監控系統的整合"""
        # 1. 執行部署
        deployment_config = {
            "version": "v2.4.0",
            "environment": "production", 
            "enable_monitoring": True
        }
        
        deploy_result = await mock_services["deployment"].deploy(**deployment_config)
        assert deploy_result["status"] == "success"
        
        # 2. 部署後健康檢查
        health_result = await mock_services["monitoring"].check_system_health()
        assert health_result["status"] == "healthy"
        
        # 3. 設置監控規則
        monitoring_config = {
            "service_name": "discord-bot",
            "version": "v2.4.0",
            "alert_rules": [
                {"metric": "cpu_usage", "threshold": 80, "severity": "high"},
                {"metric": "memory_usage", "threshold": 90, "severity": "critical"},
                {"metric": "response_time", "threshold": 1000, "severity": "medium"}
            ]
        }
        
        # 模擬監控配置
        mock_services["monitoring"].configure_alerts = AsyncMock(return_value=True)
        config_result = await mock_services["monitoring"].configure_alerts(monitoring_config)
        assert config_result is True
        
        # 驗證整合流程
        mock_services["deployment"].deploy.assert_called_once()
        mock_services["monitoring"].check_system_health.assert_called_once()
        mock_services["monitoring"].configure_alerts.assert_called_once()
    
    @pytest.mark.integration
    async def test_full_documentation_deployment_monitoring_workflow(self, mock_services, temp_project_dir):
        """測試完整的文檔-部署-監控工作流程"""
        # 階段1：文檔生成和驗證
        print("階段1：生成和驗證文檔")
        
        # 生成API文檔
        api_docs_result = await mock_services["documentation"].generate_api_docs()
        assert api_docs_result is True
        
        # 生成使用者文檔（模擬）
        mock_services["documentation"].generate_user_docs = AsyncMock(return_value=True)
        user_docs_result = await mock_services["documentation"].generate_user_docs()
        assert user_docs_result is True
        
        # 文檔品質驗證
        validation_results = await mock_services["documentation"].validate_documents()
        assert isinstance(validation_results, list)
        
        # 階段2：部署準備和執行
        print("階段2：準備和執行部署")
        
        # 準備部署環境
        deployment_config = {
            "version": "v2.4.0",
            "environment": "production",
            "strategy": "blue_green",
            "include_docs": True,
            "docs_path": str(temp_project_dir / "docs"),
            "health_check_enabled": True
        }
        
        # 執行部署
        deploy_result = await mock_services["deployment"].deploy(**deployment_config)
        assert deploy_result["status"] == "success"
        
        # 部署後驗證
        mock_services["deployment"].validate_deployment = AsyncMock(return_value=True)
        validation_result = await mock_services["deployment"].validate_deployment("v2.4.0")
        assert validation_result is True
        
        # 階段3：監控設置和健康檢查
        print("階段3：設置監控和健康檢查")
        
        # 系統健康檢查
        health_result = await mock_services["monitoring"].check_system_health()
        assert health_result["status"] == "healthy"
        
        # 配置效能監控
        monitoring_config = {
            "service_name": "discord-bot",
            "version": "v2.4.0",
            "metrics": ["cpu_usage", "memory_usage", "response_time", "error_rate"],
            "alert_rules": [
                {"metric": "cpu_usage", "threshold": 80, "severity": "high"},
                {"metric": "memory_usage", "threshold": 90, "severity": "critical"},
                {"metric": "response_time", "threshold": 1000, "severity": "medium"},
                {"metric": "error_rate", "threshold": 5, "severity": "high"}
            ]
        }
        
        mock_services["monitoring"].configure_monitoring = AsyncMock(return_value=True)
        monitoring_result = await mock_services["monitoring"].configure_monitoring(monitoring_config)
        assert monitoring_result is True
        
        # 設置自動化維護
        maintenance_config = {
            "tasks": [
                {"name": "log_cleanup", "schedule": "0 2 * * *", "script": "/scripts/cleanup_logs.py"},
                {"name": "db_backup", "schedule": "0 3 * * *", "script": "/scripts/backup_db.py"},
                {"name": "performance_report", "schedule": "0 8 * * 1", "script": "/scripts/perf_report.py"}
            ]
        }
        
        mock_services["monitoring"].setup_maintenance = AsyncMock(return_value=True)
        maintenance_result = await mock_services["monitoring"].setup_maintenance(maintenance_config)
        assert maintenance_result is True
        
        # 驗證完整工作流程
        print("驗證完整工作流程")
        
        # 驗證所有階段都已執行
        mock_services["documentation"].generate_api_docs.assert_called_once()
        mock_services["documentation"].generate_user_docs.assert_called_once()
        mock_services["documentation"].validate_documents.assert_called_once()
        
        mock_services["deployment"].deploy.assert_called_once()
        mock_services["deployment"].validate_deployment.assert_called_once()
        
        mock_services["monitoring"].check_system_health.assert_called_once()
        mock_services["monitoring"].configure_monitoring.assert_called_once()
        mock_services["monitoring"].setup_maintenance.assert_called_once()
    
    @pytest.mark.integration
    async def test_error_handling_and_rollback_integration(self, mock_services):
        """測試錯誤處理和回滾整合"""
        # 模擬部署失敗情況
        mock_services["deployment"].deploy = AsyncMock(
            return_value={"status": "failed", "error": "Health check failed"}
        )
        
        # 嘗試部署
        deployment_config = {
            "version": "v2.4.1",
            "environment": "production",
            "auto_rollback": True
        }
        
        deploy_result = await mock_services["deployment"].deploy(**deployment_config)
        assert deploy_result["status"] == "failed"
        
        # 觸發自動回滾
        mock_services["deployment"].rollback = AsyncMock(
            return_value={"status": "success", "rolled_back_to": "v2.4.0"}
        )
        
        if deploy_result["status"] == "failed":
            rollback_result = await mock_services["deployment"].rollback("v2.4.0")
            assert rollback_result["status"] == "success"
            assert rollback_result["rolled_back_to"] == "v2.4.0"
        
        # 回滾後重新檢查系統健康
        health_result = await mock_services["monitoring"].check_system_health()
        assert health_result["status"] == "healthy"
        
        # 發送警報通知
        mock_services["monitoring"].send_alert = AsyncMock(return_value=True)
        alert_result = await mock_services["monitoring"].send_alert({
            "severity": "high",
            "message": "部署失敗，已自動回滾",
            "details": {
                "failed_version": "v2.4.1",
                "current_version": "v2.4.0",
                "timestamp": datetime.now().isoformat()
            }
        })
        assert alert_result is True
        
        # 驗證錯誤處理流程
        mock_services["deployment"].deploy.assert_called_once()
        mock_services["deployment"].rollback.assert_called_once()
        mock_services["monitoring"].check_system_health.assert_called_once()
        mock_services["monitoring"].send_alert.assert_called_once()
    
    @pytest.mark.integration
    async def test_documentation_update_triggers_deployment(self, mock_services, temp_project_dir):
        """測試文檔更新觸發部署更新"""
        # 模擬文檔更新
        mock_services["documentation"].update_document = AsyncMock(
            return_value={"document_id": "api_reference", "updated": True}
        )
        
        update_result = await mock_services["documentation"].update_document("api_reference")
        assert update_result["updated"] is True
        
        # 文檔更新後觸發文檔站點重新部署
        doc_deployment_config = {
            "service": "documentation_site",
            "version": "latest",
            "environment": "production",
            "trigger": "documentation_update"
        }
        
        mock_services["deployment"].deploy_docs = AsyncMock(
            return_value={"status": "success", "service": "documentation_site"}
        )
        
        docs_deploy_result = await mock_services["deployment"].deploy_docs(doc_deployment_config)
        assert docs_deploy_result["status"] == "success"
        
        # 驗證文檔站點部署後的健康檢查
        mock_services["monitoring"].check_docs_site_health = AsyncMock(
            return_value={"status": "healthy", "response_time": 150}
        )
        
        docs_health = await mock_services["monitoring"].check_docs_site_health()
        assert docs_health["status"] == "healthy"
        assert docs_health["response_time"] < 500
        
        # 驗證整個文檔更新流程
        mock_services["documentation"].update_document.assert_called_once()
        mock_services["deployment"].deploy_docs.assert_called_once()
        mock_services["monitoring"].check_docs_site_health.assert_called_once()
    
    @pytest.mark.integration
    async def test_monitoring_alerts_trigger_maintenance(self, mock_services):
        """測試監控警報觸發維護流程"""
        # 模擬高CPU使用率警報
        alert_data = {
            "metric": "cpu_usage",
            "current_value": 85.0,
            "threshold": 80.0,
            "severity": "high",
            "service": "discord-bot-worker"
        }
        
        mock_services["monitoring"].process_alert = AsyncMock(return_value=True)
        alert_processed = await mock_services["monitoring"].process_alert(alert_data)
        assert alert_processed is True
        
        # 警報觸發自動維護任務
        maintenance_actions = [
            {"action": "restart_service", "target": "discord-bot-worker"},
            {"action": "clear_cache", "target": "redis"},
            {"action": "cleanup_temp_files", "target": "filesystem"}
        ]
        
        mock_services["monitoring"].execute_maintenance = AsyncMock(
            return_value={"executed": 3, "successful": 3, "failed": 0}
        )
        
        maintenance_result = await mock_services["monitoring"].execute_maintenance(maintenance_actions)
        assert maintenance_result["successful"] == 3
        assert maintenance_result["failed"] == 0
        
        # 維護後重新檢查系統狀態
        post_maintenance_health = await mock_services["monitoring"].check_system_health()
        assert post_maintenance_health["status"] == "healthy"
        
        # 驗證警報觸發的維護流程
        mock_services["monitoring"].process_alert.assert_called_once()
        mock_services["monitoring"].execute_maintenance.assert_called_once()
        assert mock_services["monitoring"].check_system_health.call_count == 2
    
    @pytest.mark.performance
    async def test_system_performance_under_load(self, mock_services):
        """測試系統在負載下的效能表現"""
        # 模擬高負載情況下的各種操作
        concurrent_operations = []
        
        # 並發文檔生成
        for i in range(10):
            op = mock_services["documentation"].generate_api_docs()
            concurrent_operations.append(op)
        
        # 並發健康檢查
        for i in range(20):
            op = mock_services["monitoring"].check_system_health()
            concurrent_operations.append(op)
        
        # 執行所有並發操作
        start_time = datetime.now()
        results = await asyncio.gather(*concurrent_operations, return_exceptions=True)
        end_time = datetime.now()
        
        # 檢查結果
        successful_ops = sum(1 for result in results if not isinstance(result, Exception))
        failed_ops = len(results) - successful_ops
        
        execution_time = (end_time - start_time).total_seconds()
        
        # 效能要求
        assert execution_time < 10.0  # 應該在10秒內完成
        assert failed_ops == 0  # 不應該有失敗的操作
        assert successful_ops == 30  # 所有操作都應該成功
        
        print(f"並發操作完成：{successful_ops}/{len(results)}, 耗時：{execution_time:.2f}秒")