"""
錯誤處理器單元測試套件
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

測試目標：F-4 錯誤處理和日誌系統實作
- 統一的錯誤分類、記錄和恢復機制
- 結構化日誌記錄系統
- 錯誤報告和通知機制
- 自定義錯誤類別庫

基於知識庫最佳實踐BP-002: 併發資料庫優化模式中的重試策略
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Type, Union
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from enum import Enum
from dataclasses import dataclass, field
import pytest


class ErrorSeverity(Enum):
    """錯誤嚴重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """錯誤分類"""
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    DOCKER = "docker"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """恢復行動"""
    IGNORE = "ignore"
    RETRY = "retry"
    ESCALATE = "escalate"
    FALLBACK = "fallback"
    RESTART = "restart"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class DeploymentError(Exception):
    """自定義部署錯誤類別"""
    message: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    recoverable: bool = True
    suggested_action: RecoveryAction = RecoveryAction.RETRY
    
    def __str__(self):
        return f"[{self.category.value.upper()}:{self.severity.value.upper()}] {self.message}"
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'recoverable': self.recoverable,
            'suggested_action': self.suggested_action.value,
            'exception_type': self.__class__.__name__
        }


@dataclass
class ErrorRecord:
    """錯誤記錄數據類"""
    error_id: str
    timestamp: datetime
    error_type: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    context: Dict[str, Any]
    stack_trace: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_action: Optional[RecoveryAction] = None
    resolved: bool = False
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp.isoformat(),
            'error_type': self.error_type,
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'context': self.context,
            'stack_trace': self.stack_trace,
            'recovery_attempted': self.recovery_attempted,
            'recovery_successful': self.recovery_successful,
            'recovery_action': self.recovery_action.value if self.recovery_action else None,
            'resolved': self.resolved
        }


class ErrorHandler:
    """錯誤處理器 - 統一的錯誤分類、記錄和恢復機制"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 錯誤處理配置
        self.max_retry_attempts = self.config.get('max_retry_attempts', 3)
        self.retry_delay_base = self.config.get('retry_delay_base', 1.0)  # 秒
        self.retry_exponential_backoff = self.config.get('retry_exponential_backoff', True)
        self.log_level = self.config.get('log_level', logging.INFO)
        
        # 錯誤記錄存儲
        self.error_records: List[ErrorRecord] = []
        self.error_statistics: Dict[str, int] = {}
        
        # 恢復策略註冊表
        self.recovery_strategies: Dict[ErrorCategory, Callable] = {}
        
        # 通知處理器
        self.notification_handlers: List[Callable] = []
        
        # 設置日誌記錄器
        self.logger = logging.getLogger('deployment.error_handler')
        self.logger.setLevel(self.log_level)
        
        # 註冊預設恢復策略
        self._register_default_recovery_strategies()
    
    async def handle_error(self, error: Exception, context: str = "") -> RecoveryAction:
        """
        處理錯誤並確定恢復行動
        
        參數:
            error: 發生的異常
            context: 錯誤上下文
            
        返回:
            RecoveryAction: 建議的恢復行動
        """
        try:
            # 創建錯誤記錄
            error_record = await self._create_error_record(error, context)
            
            # 記錄錯誤
            await self.log_structured_error(error_record)
            
            # 確定恢復策略
            recovery_action = await self._determine_recovery_action(error_record)
            
            # 執行恢復策略
            recovery_success = await self._execute_recovery_action(error_record, recovery_action)
            
            # 更新錯誤記錄
            error_record.recovery_attempted = True
            error_record.recovery_successful = recovery_success
            error_record.recovery_action = recovery_action
            
            # 發送通知
            await self._send_notifications(error_record)
            
            # 更新統計
            self._update_statistics(error_record)
            
            return recovery_action
            
        except Exception as handler_error:
            # 錯誤處理器本身發生錯誤
            self.logger.critical(f"ErrorHandler內部錯誤: {handler_error}")
            return RecoveryAction.MANUAL_INTERVENTION
    
    async def log_structured_error(self, error_record: ErrorRecord) -> None:
        """
        記錄結構化錯誤
        
        參數:
            error_record: 錯誤記錄對象
        """
        try:
            # 存儲錯誤記錄
            self.error_records.append(error_record)
            
            # 建構日誌訊息
            log_data = {
                'error_id': error_record.error_id,
                'category': error_record.category.value,
                'severity': error_record.severity.value,
                'message': error_record.message,
                'context': error_record.context,
                'timestamp': error_record.timestamp.isoformat()
            }
            
            # 根據嚴重程度選擇日誌級別
            if error_record.severity == ErrorSeverity.CRITICAL:
                self.logger.critical(f"CRITICAL ERROR: {json.dumps(log_data, ensure_ascii=False)}")
            elif error_record.severity == ErrorSeverity.HIGH:
                self.logger.error(f"HIGH ERROR: {json.dumps(log_data, ensure_ascii=False)}")
            elif error_record.severity == ErrorSeverity.MEDIUM:
                self.logger.warning(f"MEDIUM ERROR: {json.dumps(log_data, ensure_ascii=False)}")
            else:
                self.logger.info(f"LOW ERROR: {json.dumps(log_data, ensure_ascii=False)}")
            
            # 如果有堆疊追蹤，記錄詳細資訊
            if error_record.stack_trace:
                self.logger.debug(f"Stack trace for {error_record.error_id}: {error_record.stack_trace}")
                
        except Exception as e:
            # 日誌記錄失敗，使用基本日誌
            self.logger.error(f"結構化日誌記錄失敗: {e}")
    
    async def suggest_resolution(self, error_type: str) -> List[str]:
        """
        建議錯誤解決方案
        
        參數:
            error_type: 錯誤類型
            
        返回:
            List[str]: 建議解決方案列表
        """
        # 解決方案知識庫
        resolution_knowledge_base = {
            'ConnectionError': [
                "檢查網路連接狀態",
                "驗證服務端點是否可達",
                "檢查防火牆設定",
                "確認服務是否正在運行"
            ],
            'DockerError': [
                "檢查Docker daemon是否運行",
                "驗證Docker Compose文件語法",
                "檢查映像是否存在",
                "確認端口是否被占用"
            ],
            'DatabaseError': [
                "檢查資料庫連接字串",
                "驗證資料庫服務狀態",
                "檢查權限和認證",
                "確認資料庫磁盤空間"
            ],
            'ConfigurationError': [
                "檢查配置文件格式",
                "驗證必要參數",
                "檢查環境變數",
                "確認文件權限"
            ],
            'TimeoutError': [
                "增加超時時間限制",
                "檢查系統負載",
                "優化操作性能",
                "考慮使用非同步處理"
            ]
        }
        
        # 通用解決方案
        generic_solutions = [
            "檢查系統日誌獲取更多資訊",
            "重啟相關服務",
            "檢查系統資源使用情況",
            "聯繫系統管理員"
        ]
        
        # 根據錯誤類型返回建議
        suggestions = resolution_knowledge_base.get(error_type, [])
        if not suggestions:
            # 嘗試根據錯誤名稱匹配
            for known_error, solutions in resolution_knowledge_base.items():
                if known_error.lower() in error_type.lower():
                    suggestions = solutions
                    break
        
        # 如果還是沒有找到，返回通用解決方案
        if not suggestions:
            suggestions = generic_solutions
        
        return suggestions
    
    def register_recovery_strategy(self, category: ErrorCategory, strategy: Callable) -> None:
        """
        註冊錯誤恢復策略
        
        參數:
            category: 錯誤分類
            strategy: 恢復策略函數
        """
        self.recovery_strategies[category] = strategy
        self.logger.info(f"註冊恢復策略: {category.value}")
    
    def register_notification_handler(self, handler: Callable) -> None:
        """
        註冊通知處理器
        
        參數:
            handler: 通知處理函數
        """
        self.notification_handlers.append(handler)
        self.logger.info("註冊通知處理器")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        獲取錯誤統計資訊
        
        返回:
            Dict[str, Any]: 錯誤統計數據
        """
        total_errors = len(self.error_records)
        if total_errors == 0:
            return {
                'total_errors': 0,
                'by_category': {},
                'by_severity': {},
                'recovery_success_rate': 0.0,
                'most_common_errors': []
            }
        
        # 按分類統計
        by_category = {}
        for record in self.error_records:
            category = record.category.value
            by_category[category] = by_category.get(category, 0) + 1
        
        # 按嚴重程度統計
        by_severity = {}
        for record in self.error_records:
            severity = record.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # 恢復成功率
        recovery_attempted = len([r for r in self.error_records if r.recovery_attempted])
        recovery_successful = len([r for r in self.error_records if r.recovery_successful])
        recovery_success_rate = (recovery_successful / recovery_attempted * 100) if recovery_attempted > 0 else 0.0
        
        # 最常見錯誤
        most_common_errors = sorted(self.error_statistics.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_errors': total_errors,
            'by_category': by_category,
            'by_severity': by_severity,
            'recovery_success_rate': recovery_success_rate,
            'most_common_errors': most_common_errors
        }
    
    def get_recent_errors(self, hours: int = 24) -> List[ErrorRecord]:
        """
        獲取最近的錯誤記錄
        
        參數:
            hours: 時間範圍（小時）
            
        返回:
            List[ErrorRecord]: 錯誤記錄列表
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [record for record in self.error_records if record.timestamp >= cutoff_time]
    
    def clear_resolved_errors(self) -> int:
        """
        清理已解決的錯誤記錄
        
        返回:
            int: 清理的記錄數量
        """
        initial_count = len(self.error_records)
        self.error_records = [record for record in self.error_records if not record.resolved]
        cleared_count = initial_count - len(self.error_records)
        
        self.logger.info(f"清理了 {cleared_count} 個已解決的錯誤記錄")
        return cleared_count
    
    async def _create_error_record(self, error: Exception, context: str) -> ErrorRecord:
        """創建錯誤記錄"""
        error_id = f"err_{int(datetime.now().timestamp() * 1000)}"
        
        # 確定錯誤分類和嚴重程度
        category, severity = self._classify_error(error)
        
        # 建構上下文資訊
        error_context = {
            'context': context,
            'error_class': error.__class__.__name__,
            'error_module': error.__class__.__module__ if hasattr(error.__class__, '__module__') else 'unknown'
        }
        
        # 如果是自定義錯誤，使用其context
        if isinstance(error, DeploymentError):
            error_context.update(error.context)
            category = error.category
            severity = error.severity
        
        # 獲取堆疊追蹤
        stack_trace = traceback.format_exc() if hasattr(error, '__traceback__') else None
        
        return ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(),
            error_type=error.__class__.__name__,
            message=str(error),
            category=category,
            severity=severity,
            context=error_context,
            stack_trace=stack_trace
        )
    
    def _classify_error(self, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """錯誤分類和嚴重程度判定"""
        error_type = error.__class__.__name__
        error_message = str(error).lower()
        
        # 網路相關錯誤
        if any(keyword in error_type.lower() for keyword in ['connection', 'timeout', 'network']):
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        
        # Docker相關錯誤
        if any(keyword in error_message for keyword in ['docker', 'container', 'compose']):
            return ErrorCategory.DOCKER, ErrorSeverity.HIGH
        
        # 資料庫相關錯誤
        if any(keyword in error_type.lower() for keyword in ['database', 'sql', 'db']):
            return ErrorCategory.DATABASE, ErrorSeverity.HIGH
        
        # 配置相關錯誤
        if any(keyword in error_type.lower() for keyword in ['config', 'setting', 'environment']):
            return ErrorCategory.CONFIGURATION, ErrorSeverity.MEDIUM
        
        # 權限和安全錯誤
        if any(keyword in error_type.lower() for keyword in ['permission', 'access', 'auth', 'security']):
            return ErrorCategory.SECURITY, ErrorSeverity.HIGH
        
        # 系統級錯誤
        if any(keyword in error_type.lower() for keyword in ['system', 'os', 'memory', 'disk']):
            return ErrorCategory.SYSTEM, ErrorSeverity.CRITICAL
        
        # 預設分類
        return ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM
    
    async def _determine_recovery_action(self, error_record: ErrorRecord) -> RecoveryAction:
        """確定恢復行動"""
        # 如果是自定義錯誤且有建議行動
        if hasattr(error_record, 'suggested_action'):
            return error_record.suggested_action
        
        # 根據錯誤分類確定行動
        category_actions = {
            ErrorCategory.NETWORK: RecoveryAction.RETRY,
            ErrorCategory.DOCKER: RecoveryAction.RESTART,
            ErrorCategory.DATABASE: RecoveryAction.RETRY,
            ErrorCategory.CONFIGURATION: RecoveryAction.MANUAL_INTERVENTION,
            ErrorCategory.SECURITY: RecoveryAction.ESCALATE,
            ErrorCategory.SYSTEM: RecoveryAction.ESCALATE,
            ErrorCategory.UNKNOWN: RecoveryAction.RETRY
        }
        
        # 根據嚴重程度調整
        if error_record.severity == ErrorSeverity.CRITICAL:
            return RecoveryAction.ESCALATE
        elif error_record.severity == ErrorSeverity.LOW:
            return RecoveryAction.IGNORE
        
        return category_actions.get(error_record.category, RecoveryAction.RETRY)
    
    async def _execute_recovery_action(self, error_record: ErrorRecord, action: RecoveryAction) -> bool:
        """執行恢復行動"""
        try:
            if action == RecoveryAction.IGNORE:
                return True
            elif action == RecoveryAction.RETRY:
                return await self._execute_retry_strategy(error_record)
            elif action == RecoveryAction.RESTART:
                return await self._execute_restart_strategy(error_record)
            elif action == RecoveryAction.FALLBACK:
                return await self._execute_fallback_strategy(error_record)
            elif action in [RecoveryAction.ESCALATE, RecoveryAction.MANUAL_INTERVENTION]:
                # 這些行動不能自動執行，返回False表示需要人工介入
                return False
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"執行恢復行動失敗: {e}")
            return False
    
    async def _execute_retry_strategy(self, error_record: ErrorRecord) -> bool:
        """執行重試策略"""
        # 檢查是否已經達到最大重試次數
        retry_count = error_record.context.get('retry_count', 0)
        if retry_count >= self.max_retry_attempts:
            return False
        
        # 計算延遲時間
        if self.retry_exponential_backoff:
            delay = self.retry_delay_base * (2 ** retry_count)
        else:
            delay = self.retry_delay_base
        
        # 等待延遲
        await asyncio.sleep(delay)
        
        # 更新重試次數
        error_record.context['retry_count'] = retry_count + 1
        
        # 返回True表示可以重試
        return True
    
    async def _execute_restart_strategy(self, error_record: ErrorRecord) -> bool:
        """執行重啟策略"""
        # 這裡應該實現實際的重啟邏輯
        # 對於測試，我們簡化處理
        self.logger.info(f"執行重啟策略: {error_record.error_id}")
        return True
    
    async def _execute_fallback_strategy(self, error_record: ErrorRecord) -> bool:
        """執行降級策略"""
        # 這裡應該實現實際的降級邏輯
        # 對於測試，我們簡化處理
        self.logger.info(f"執行降級策略: {error_record.error_id}")
        return True
    
    async def _send_notifications(self, error_record: ErrorRecord) -> None:
        """發送通知"""
        for handler in self.notification_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error_record)
                else:
                    handler(error_record)
            except Exception as e:
                self.logger.error(f"通知發送失敗: {e}")
    
    def _update_statistics(self, error_record: ErrorRecord) -> None:
        """更新錯誤統計"""
        error_key = error_record.error_type
        self.error_statistics[error_key] = self.error_statistics.get(error_key, 0) + 1
    
    def _register_default_recovery_strategies(self) -> None:
        """註冊預設恢復策略"""
        # 這裡可以註冊一些預設的恢復策略
        pass


class TestErrorHandler:
    """錯誤處理器測試類"""
    
    @pytest.fixture
    def error_handler(self):
        """測試固件：創建錯誤處理器實例"""
        config = {
            'max_retry_attempts': 3,
            'retry_delay_base': 0.1,  # 測試中使用較短的延遲
            'retry_exponential_backoff': True,
            'log_level': logging.DEBUG
        }
        return ErrorHandler(config)
    
    @pytest.fixture
    def sample_deployment_error(self):
        """測試固件：示例部署錯誤"""
        return DeploymentError(
            message="Docker容器啟動失敗",
            category=ErrorCategory.DOCKER,
            severity=ErrorSeverity.HIGH,
            context={'container': 'discord-bot', 'exit_code': 1},
            recoverable=True,
            suggested_action=RecoveryAction.RESTART
        )
    
    @pytest.fixture
    def sample_error_record(self):
        """測試固件：示例錯誤記錄"""
        return ErrorRecord(
            error_id="test_error_123",
            timestamp=datetime.now(),
            error_type="ConnectionError",
            message="連接超時",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            context={'host': 'localhost', 'port': 6379}
        )
    
    class TestErrorClassification:
        """錯誤分類測試"""
        
        def test_classify_network_error(self, error_handler):
            """測試：網路錯誤分類"""
            error = ConnectionError("Connection timeout")
            category, severity = error_handler._classify_error(error)
            
            assert category == ErrorCategory.NETWORK
            assert severity == ErrorSeverity.MEDIUM
        
        def test_classify_docker_error(self, error_handler):
            """測試：Docker錯誤分類"""
            error = Exception("Docker daemon not running")
            category, severity = error_handler._classify_error(error)
            
            assert category == ErrorCategory.DOCKER
            assert severity == ErrorSeverity.HIGH
        
        def test_classify_database_error(self, error_handler):
            """測試：資料庫錯誤分類"""
            error = Exception("DatabaseError: connection failed")
            category, severity = error_handler._classify_error(error)
            
            assert category == ErrorCategory.DATABASE
            assert severity == ErrorSeverity.HIGH
        
        def test_classify_system_error(self, error_handler):
            """測試：系統錯誤分類"""
            error = MemoryError("Out of memory")
            category, severity = error_handler._classify_error(error)
            
            assert category == ErrorCategory.SYSTEM
            assert severity == ErrorSeverity.CRITICAL
        
        def test_classify_unknown_error(self, error_handler):
            """測試：未知錯誤分類"""
            error = ValueError("Invalid value")
            category, severity = error_handler._classify_error(error)
            
            assert category == ErrorCategory.UNKNOWN
            assert severity == ErrorSeverity.MEDIUM
    
    class TestErrorHandling:
        """錯誤處理測試"""
        
        @pytest.mark.asyncio
        async def test_handle_error_success(self, error_handler, sample_deployment_error):
            """測試：成功處理錯誤"""
            with patch.object(error_handler, '_execute_recovery_action', return_value=True):
                
                recovery_action = await error_handler.handle_error(sample_deployment_error, "test context")
                
                assert recovery_action == RecoveryAction.RESTART
                assert len(error_handler.error_records) == 1
                
                error_record = error_handler.error_records[0]
                assert error_record.message == "Docker容器啟動失敗"
                assert error_record.category == ErrorCategory.DOCKER
                assert error_record.recovery_attempted is True
                assert error_record.recovery_successful is True
        
        @pytest.mark.asyncio
        async def test_handle_error_recovery_failure(self, error_handler):
            """測試：恢復失敗的錯誤處理"""
            test_error = Exception("Test error")
            
            with patch.object(error_handler, '_execute_recovery_action', return_value=False):
                
                recovery_action = await error_handler.handle_error(test_error, "test context")
                
                assert recovery_action == RecoveryAction.RETRY  # 預設行動
                
                error_record = error_handler.error_records[0]
                assert error_record.recovery_attempted is True
                assert error_record.recovery_successful is False
        
        @pytest.mark.asyncio
        async def test_handle_error_handler_exception(self, error_handler):
            """測試：錯誤處理器內部異常"""
            test_error = Exception("Test error")
            
            with patch.object(error_handler, '_create_error_record', side_effect=Exception("Handler error")):
                
                recovery_action = await error_handler.handle_error(test_error, "test context")
                
                assert recovery_action == RecoveryAction.MANUAL_INTERVENTION
        
        @pytest.mark.asyncio
        async def test_create_error_record(self, error_handler):
            """測試：創建錯誤記錄"""
            test_error = ConnectionError("Connection failed")
            context = "testing connection"
            
            error_record = await error_handler._create_error_record(test_error, context)
            
            assert error_record.error_type == "ConnectionError"
            assert error_record.message == "Connection failed"
            assert error_record.category == ErrorCategory.NETWORK
            assert error_record.severity == ErrorSeverity.MEDIUM
            assert error_record.context['context'] == context
            assert error_record.error_id.startswith("err_")
        
        @pytest.mark.asyncio
        async def test_create_error_record_custom_error(self, error_handler, sample_deployment_error):
            """測試：創建自定義錯誤記錄"""
            error_record = await error_handler._create_error_record(sample_deployment_error, "test")
            
            assert error_record.category == ErrorCategory.DOCKER
            assert error_record.severity == ErrorSeverity.HIGH
            assert 'container' in error_record.context
            assert error_record.context['container'] == 'discord-bot'
    
    class TestLogging:
        """日誌記錄測試"""
        
        @pytest.mark.asyncio
        async def test_log_structured_error(self, error_handler, sample_error_record):
            """測試：結構化錯誤日誌記錄"""
            with patch.object(error_handler.logger, 'warning') as mock_logger:
                
                await error_handler.log_structured_error(sample_error_record)
                
                assert len(error_handler.error_records) == 1
                mock_logger.assert_called_once()
                
                # 檢查日誌內容
                log_call = mock_logger.call_args[0][0]
                assert "MEDIUM ERROR" in log_call
                assert sample_error_record.error_id in log_call
        
        @pytest.mark.asyncio
        async def test_log_structured_error_critical(self, error_handler):
            """測試：關鍵錯誤日誌記錄"""
            critical_record = ErrorRecord(
                error_id="critical_test",
                timestamp=datetime.now(),
                error_type="SystemError",
                message="System failure",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                context={}
            )
            
            with patch.object(error_handler.logger, 'critical') as mock_logger:
                
                await error_handler.log_structured_error(critical_record)
                
                mock_logger.assert_called_once()
                log_call = mock_logger.call_args[0][0]
                assert "CRITICAL ERROR" in log_call
        
        @pytest.mark.asyncio
        async def test_log_structured_error_with_stack_trace(self, error_handler):
            """測試：帶堆疊追蹤的錯誤日誌"""
            error_record = ErrorRecord(
                error_id="stack_test",
                timestamp=datetime.now(),
                error_type="TestError",
                message="Test with stack",
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.LOW,
                context={},
                stack_trace="Traceback: line 1\n  line 2"
            )
            
            with patch.object(error_handler.logger, 'info') as mock_info, \
                 patch.object(error_handler.logger, 'debug') as mock_debug:
                
                await error_handler.log_structured_error(error_record)
                
                mock_info.assert_called_once()
                mock_debug.assert_called_once()
                
                # 檢查堆疊追蹤日誌
                debug_call = mock_debug.call_args[0][0]
                assert "Stack trace for stack_test" in debug_call
        
        @pytest.mark.asyncio
        async def test_log_structured_error_exception(self, error_handler, sample_error_record):
            """測試：日誌記錄異常處理"""
            with patch.object(error_handler, 'error_records', side_effect=Exception("Log error")), \
                 patch.object(error_handler.logger, 'error') as mock_error:
                
                await error_handler.log_structured_error(sample_error_record)
                
                mock_error.assert_called()
                error_call = mock_error.call_args[0][0]
                assert "結構化日誌記錄失敗" in error_call
    
    class TestRecoveryStrategies:
        """恢復策略測試"""
        
        @pytest.mark.asyncio
        async def test_determine_recovery_action_by_category(self, error_handler):
            """測試：根據錯誤分類確定恢復行動"""
            network_record = ErrorRecord("net1", datetime.now(), "ConnectionError", "msg", 
                                       ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, {})
            
            action = await error_handler._determine_recovery_action(network_record)
            assert action == RecoveryAction.RETRY
            
            docker_record = ErrorRecord("dock1", datetime.now(), "DockerError", "msg",
                                      ErrorCategory.DOCKER, ErrorSeverity.HIGH, {})
            
            action = await error_handler._determine_recovery_action(docker_record)
            assert action == RecoveryAction.RESTART
        
        @pytest.mark.asyncio
        async def test_determine_recovery_action_critical_severity(self, error_handler):
            """測試：關鍵嚴重程度錯誤的恢復行動"""
            critical_record = ErrorRecord("crit1", datetime.now(), "CriticalError", "msg",
                                        ErrorCategory.NETWORK, ErrorSeverity.CRITICAL, {})
            
            action = await error_handler._determine_recovery_action(critical_record)
            assert action == RecoveryAction.ESCALATE
        
        @pytest.mark.asyncio
        async def test_determine_recovery_action_low_severity(self, error_handler):
            """測試：低嚴重程度錯誤的恢復行動"""
            low_record = ErrorRecord("low1", datetime.now(), "MinorError", "msg",
                                   ErrorCategory.UNKNOWN, ErrorSeverity.LOW, {})
            
            action = await error_handler._determine_recovery_action(low_record)
            assert action == RecoveryAction.IGNORE
        
        @pytest.mark.asyncio
        async def test_execute_retry_strategy_success(self, error_handler, sample_error_record):
            """測試：成功執行重試策略"""
            with patch('asyncio.sleep') as mock_sleep:
                
                result = await error_handler._execute_retry_strategy(sample_error_record)
                
                assert result is True
                assert sample_error_record.context['retry_count'] == 1
                mock_sleep.assert_called_once()
        
        @pytest.mark.asyncio
        async def test_execute_retry_strategy_max_retries(self, error_handler, sample_error_record):
            """測試：達到最大重試次數"""
            sample_error_record.context['retry_count'] = 3  # 已達最大重試次數
            
            result = await error_handler._execute_retry_strategy(sample_error_record)
            
            assert result is False
        
        @pytest.mark.asyncio
        async def test_execute_retry_strategy_exponential_backoff(self, error_handler, sample_error_record):
            """測試：指數退避重試策略"""
            sample_error_record.context['retry_count'] = 2
            
            with patch('asyncio.sleep') as mock_sleep:
                
                await error_handler._execute_retry_strategy(sample_error_record)
                
                # 計算期望的延遲時間：base * (2 ** retry_count) = 0.1 * (2 ** 2) = 0.4
                expected_delay = 0.1 * (2 ** 2)
                mock_sleep.assert_called_once_with(expected_delay)
        
        @pytest.mark.asyncio
        async def test_execute_restart_strategy(self, error_handler, sample_error_record):
            """測試：執行重啟策略"""
            result = await error_handler._execute_restart_strategy(sample_error_record)
            assert result is True
        
        @pytest.mark.asyncio
        async def test_execute_fallback_strategy(self, error_handler, sample_error_record):
            """測試：執行降級策略"""
            result = await error_handler._execute_fallback_strategy(sample_error_record)
            assert result is True
        
        @pytest.mark.asyncio
        async def test_execute_recovery_action_ignore(self, error_handler, sample_error_record):
            """測試：執行忽略恢復行動"""
            result = await error_handler._execute_recovery_action(sample_error_record, RecoveryAction.IGNORE)
            assert result is True
        
        @pytest.mark.asyncio
        async def test_execute_recovery_action_escalate(self, error_handler, sample_error_record):
            """測試：執行升級恢復行動"""
            result = await error_handler._execute_recovery_action(sample_error_record, RecoveryAction.ESCALATE)
            assert result is False  # 需要人工介入
        
        @pytest.mark.asyncio
        async def test_execute_recovery_action_exception(self, error_handler, sample_error_record):
            """測試：恢復行動執行異常"""
            with patch.object(error_handler, '_execute_retry_strategy', side_effect=Exception("Recovery error")):
                
                result = await error_handler._execute_recovery_action(sample_error_record, RecoveryAction.RETRY)
                
                assert result is False
    
    class TestResolutionSuggestions:
        """解決方案建議測試"""
        
        @pytest.mark.asyncio
        async def test_suggest_resolution_known_error(self, error_handler):
            """測試：已知錯誤類型的解決方案建議"""
            suggestions = await error_handler.suggest_resolution('ConnectionError')
            
            assert len(suggestions) > 0
            assert any('網路連接' in suggestion for suggestion in suggestions)
            assert any('服務端點' in suggestion for suggestion in suggestions)
        
        @pytest.mark.asyncio
        async def test_suggest_resolution_docker_error(self, error_handler):
            """測試：Docker錯誤的解決方案建議"""
            suggestions = await error_handler.suggest_resolution('DockerError')
            
            assert len(suggestions) > 0
            assert any('Docker daemon' in suggestion for suggestion in suggestions)
            assert any('Docker Compose' in suggestion for suggestion in suggestions)
        
        @pytest.mark.asyncio
        async def test_suggest_resolution_partial_match(self, error_handler):
            """測試：部分匹配錯誤類型的建議"""
            suggestions = await error_handler.suggest_resolution('CustomTimeoutError')
            
            # 應該匹配到 'TimeoutError' 的建議
            assert len(suggestions) > 0
            assert any('超時時間限制' in suggestion for suggestion in suggestions)
        
        @pytest.mark.asyncio
        async def test_suggest_resolution_unknown_error(self, error_handler):
            """測試：未知錯誤類型的通用建議"""
            suggestions = await error_handler.suggest_resolution('UnknownError')
            
            # 應該返回通用解決方案
            assert len(suggestions) > 0
            assert any('系統日誌' in suggestion for suggestion in suggestions)
            assert any('系統管理員' in suggestion for suggestion in suggestions)
    
    class TestNotifications:
        """通知測試"""
        
        @pytest.mark.asyncio
        async def test_register_notification_handler(self, error_handler):
            """測試：註冊通知處理器"""
            def test_handler(error_record):
                pass
            
            error_handler.register_notification_handler(test_handler)
            
            assert len(error_handler.notification_handlers) == 1
            assert test_handler in error_handler.notification_handlers
        
        @pytest.mark.asyncio
        async def test_send_notifications_sync_handler(self, error_handler, sample_error_record):
            """測試：發送通知到同步處理器"""
            notification_calls = []
            
            def sync_handler(error_record):
                notification_calls.append(error_record.error_id)
            
            error_handler.register_notification_handler(sync_handler)
            
            await error_handler._send_notifications(sample_error_record)
            
            assert len(notification_calls) == 1
            assert notification_calls[0] == sample_error_record.error_id
        
        @pytest.mark.asyncio
        async def test_send_notifications_async_handler(self, error_handler, sample_error_record):
            """測試：發送通知到異步處理器"""
            notification_calls = []
            
            async def async_handler(error_record):
                notification_calls.append(error_record.error_id)
            
            error_handler.register_notification_handler(async_handler)
            
            await error_handler._send_notifications(sample_error_record)
            
            assert len(notification_calls) == 1
            assert notification_calls[0] == sample_error_record.error_id
        
        @pytest.mark.asyncio
        async def test_send_notifications_handler_exception(self, error_handler, sample_error_record):
            """測試：通知處理器異常處理"""
            def failing_handler(error_record):
                raise Exception("Notification failed")
            
            error_handler.register_notification_handler(failing_handler)
            
            # 應該不拋出異常
            await error_handler._send_notifications(sample_error_record)
    
    class TestStatistics:
        """統計測試"""
        
        def test_get_error_statistics_empty(self, error_handler):
            """測試：空錯誤記錄的統計"""
            stats = error_handler.get_error_statistics()
            
            assert stats['total_errors'] == 0
            assert stats['by_category'] == {}
            assert stats['by_severity'] == {}
            assert stats['recovery_success_rate'] == 0.0
            assert stats['most_common_errors'] == []
        
        def test_get_error_statistics_with_data(self, error_handler):
            """測試：有數據的錯誤統計"""
            # 添加測試錯誤記錄
            records = [
                ErrorRecord("1", datetime.now(), "ConnectionError", "msg1", 
                          ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, {}, 
                          recovery_attempted=True, recovery_successful=True),
                ErrorRecord("2", datetime.now(), "DockerError", "msg2", 
                          ErrorCategory.DOCKER, ErrorSeverity.HIGH, {},
                          recovery_attempted=True, recovery_successful=False),
                ErrorRecord("3", datetime.now(), "ConnectionError", "msg3", 
                          ErrorCategory.NETWORK, ErrorSeverity.LOW, {},
                          recovery_attempted=False)
            ]
            
            error_handler.error_records = records
            error_handler.error_statistics = {"ConnectionError": 2, "DockerError": 1}
            
            stats = error_handler.get_error_statistics()
            
            assert stats['total_errors'] == 3
            assert stats['by_category']['network'] == 2
            assert stats['by_category']['docker'] == 1
            assert stats['by_severity']['medium'] == 1
            assert stats['by_severity']['high'] == 1
            assert stats['by_severity']['low'] == 1
            assert stats['recovery_success_rate'] == 50.0  # 1 success out of 2 attempts
            assert stats['most_common_errors'][0] == ("ConnectionError", 2)
        
        def test_get_recent_errors(self, error_handler):
            """測試：獲取最近的錯誤記錄"""
            now = datetime.now()
            old_time = now - timedelta(hours=25)  # 25小時前
            recent_time = now - timedelta(hours=1)  # 1小時前
            
            old_record = ErrorRecord("old", old_time, "OldError", "msg", 
                                   ErrorCategory.UNKNOWN, ErrorSeverity.LOW, {})
            recent_record = ErrorRecord("recent", recent_time, "RecentError", "msg", 
                                      ErrorCategory.UNKNOWN, ErrorSeverity.LOW, {})
            
            error_handler.error_records = [old_record, recent_record]
            
            recent_errors = error_handler.get_recent_errors(hours=24)
            
            assert len(recent_errors) == 1
            assert recent_errors[0].error_id == "recent"
        
        def test_clear_resolved_errors(self, error_handler):
            """測試：清理已解決的錯誤"""
            resolved_record = ErrorRecord("resolved", datetime.now(), "ResolvedError", "msg",
                                        ErrorCategory.UNKNOWN, ErrorSeverity.LOW, {},
                                        resolved=True)
            unresolved_record = ErrorRecord("unresolved", datetime.now(), "UnresolvedError", "msg",
                                          ErrorCategory.UNKNOWN, ErrorSeverity.LOW, {},
                                          resolved=False)
            
            error_handler.error_records = [resolved_record, unresolved_record]
            
            cleared_count = error_handler.clear_resolved_errors()
            
            assert cleared_count == 1
            assert len(error_handler.error_records) == 1
            assert error_handler.error_records[0].error_id == "unresolved"
        
        def test_update_statistics(self, error_handler, sample_error_record):
            """測試：更新錯誤統計"""
            error_handler._update_statistics(sample_error_record)
            
            assert error_handler.error_statistics["ConnectionError"] == 1
            
            # 再次更新同類型錯誤
            error_handler._update_statistics(sample_error_record)
            
            assert error_handler.error_statistics["ConnectionError"] == 2
    
    class TestCustomErrorTypes:
        """自定義錯誤類型測試"""
        
        def test_deployment_error_creation(self, sample_deployment_error):
            """測試：創建部署錯誤"""
            assert str(sample_deployment_error) == "[DOCKER:HIGH] Docker容器啟動失敗"
            assert sample_deployment_error.category == ErrorCategory.DOCKER
            assert sample_deployment_error.severity == ErrorSeverity.HIGH
            assert sample_deployment_error.recoverable is True
            assert sample_deployment_error.suggested_action == RecoveryAction.RESTART
        
        def test_deployment_error_to_dict(self, sample_deployment_error):
            """測試：部署錯誤轉換為字典"""
            error_dict = sample_deployment_error.to_dict()
            
            assert error_dict['message'] == "Docker容器啟動失敗"
            assert error_dict['category'] == 'docker'
            assert error_dict['severity'] == 'high'
            assert error_dict['recoverable'] is True
            assert error_dict['suggested_action'] == 'restart'
            assert 'timestamp' in error_dict
            assert error_dict['exception_type'] == 'DeploymentError'
        
        def test_error_record_to_dict(self, sample_error_record):
            """測試：錯誤記錄轉換為字典"""
            record_dict = sample_error_record.to_dict()
            
            assert record_dict['error_id'] == "test_error_123"
            assert record_dict['error_type'] == "ConnectionError"
            assert record_dict['message'] == "連接超時"
            assert record_dict['category'] == 'network'
            assert record_dict['severity'] == 'medium'
            assert 'timestamp' in record_dict
            assert record_dict['context']['host'] == 'localhost'
    
    class TestRecoveryStrategyRegistration:
        """恢復策略註冊測試"""
        
        def test_register_recovery_strategy(self, error_handler):
            """測試：註冊恢復策略"""
            def custom_recovery(error_record):
                return True
            
            error_handler.register_recovery_strategy(ErrorCategory.NETWORK, custom_recovery)
            
            assert ErrorCategory.NETWORK in error_handler.recovery_strategies
            assert error_handler.recovery_strategies[ErrorCategory.NETWORK] == custom_recovery
    
    class TestConfiguration:
        """配置測試"""
        
        def test_default_configuration(self):
            """測試：預設配置"""
            handler = ErrorHandler()
            
            assert handler.max_retry_attempts == 3
            assert handler.retry_delay_base == 1.0
            assert handler.retry_exponential_backoff is True
            assert handler.log_level == logging.INFO
        
        def test_custom_configuration(self):
            """測試：自定義配置"""
            config = {
                'max_retry_attempts': 5,
                'retry_delay_base': 2.0,
                'retry_exponential_backoff': False,
                'log_level': logging.DEBUG
            }
            
            handler = ErrorHandler(config)
            
            assert handler.max_retry_attempts == 5
            assert handler.retry_delay_base == 2.0
            assert handler.retry_exponential_backoff is False
            assert handler.log_level == logging.DEBUG


if __name__ == '__main__':
    pytest.main([__file__, '-v'])