#!/usr/bin/env python3
"""
錯誤處理器 - 統一的錯誤分類、記錄和恢復機制
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組負責統一處理部署過程中的各種錯誤，提供分類、日誌記錄、診斷和恢復建議。
"""

import json
import logging
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """錯誤嚴重性等級"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """錯誤分類"""
    ENVIRONMENT = "environment"      # 環境問題
    DOCKER = "docker"               # Docker相關
    NETWORK = "network"             # 網路問題
    CONFIGURATION = "configuration" # 配置錯誤
    PERMISSION = "permission"       # 權限問題
    RESOURCE = "resource"           # 資源不足
    SERVICE = "service"             # 服務故障
    DEPENDENCY = "dependency"       # 依賴問題
    UNKNOWN = "unknown"             # 未知錯誤


@dataclass
class DeploymentError:
    """部署錯誤"""
    error_id: str
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    title: str
    message: str
    context: Dict[str, Any]
    stack_trace: Optional[str] = None
    resolution_steps: List[str] = None
    auto_recovery_attempted: bool = False
    resolved: bool = False
    resolution_time: Optional[datetime] = None


@dataclass
class RecoveryAction:
    """恢復動作"""
    action_type: str
    description: str
    command: Optional[str] = None
    timeout_seconds: int = 30
    retry_attempts: int = 1
    success_criteria: Optional[str] = None


@dataclass
class ErrorReport:
    """錯誤報告"""
    timestamp: datetime
    total_errors: int
    error_by_category: Dict[str, int]
    error_by_severity: Dict[str, int]
    recent_errors: List[DeploymentError]
    resolution_success_rate: float
    recommendations: List[str]


class ErrorHandler:
    """
    錯誤處理器 - 統一的錯誤分類、記錄和恢復機制
    
    功能：
    - 錯誤分類和嚴重性評估
    - 結構化日誌記錄
    - 自動故障診斷
    - 恢復建議生成
    - 錯誤統計和報告
    """
    
    def __init__(self, project_root: Optional[Path] = None, db_path: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.db_path = db_path or (self.project_root / 'data' / 'errors.db')
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 錯誤分類規則
        self.classification_rules = self._build_classification_rules()
        
        # 恢復策略映射
        self.recovery_strategies = self._build_recovery_strategies()
        
        self._ensure_database()
    
    def _ensure_database(self) -> None:
        """確保錯誤資料庫存在並初始化"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deployment_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_id TEXT UNIQUE NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context TEXT,  -- JSON
                    stack_trace TEXT,
                    resolution_steps TEXT,  -- JSON
                    auto_recovery_attempted BOOLEAN DEFAULT FALSE,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolution_time DATETIME
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS recovery_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    command TEXT,
                    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN,
                    execution_time_ms INTEGER,
                    output TEXT,
                    error_message TEXT,
                    FOREIGN KEY (error_id) REFERENCES deployment_errors (error_id)
                )
            ''')
            
            conn.commit()
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> RecoveryAction:
        """
        處理錯誤
        
        Args:
            error: 異常物件
            context: 錯誤上下文資訊
            
        Returns:
            RecoveryAction: 恢復動作
        """
        # 生成錯誤ID
        error_id = self._generate_error_id(error, context)
        
        # 分類錯誤
        category, severity = self._classify_error(error, context)
        
        # 創建錯誤記錄
        deployment_error = DeploymentError(
            error_id=error_id,
            timestamp=datetime.now(),
            category=category,
            severity=severity,
            title=self._extract_error_title(error),
            message=str(error),
            context=context,
            stack_trace=traceback.format_exc(),
            resolution_steps=self._generate_resolution_steps(error, context, category)
        )
        
        # 記錄錯誤
        await self.log_structured_error(deployment_error)
        
        # 生成恢復動作
        recovery_action = self._suggest_recovery_action(deployment_error)
        
        # 如果是自動可恢復的錯誤，標記已嘗試自動恢復
        if self._is_auto_recoverable(category, severity):
            deployment_error.auto_recovery_attempted = True
            await self._update_error_status(error_id, auto_recovery_attempted=True)
        
        self.logger.info(f"錯誤處理完成: {error_id}, 建議動作: {recovery_action.action_type}")
        return recovery_action
    
    async def log_structured_error(self, error: DeploymentError) -> None:
        """
        記錄結構化錯誤
        
        Args:
            error: 部署錯誤物件
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO deployment_errors (
                        error_id, category, severity, title, message, context,
                        stack_trace, resolution_steps, auto_recovery_attempted,
                        resolved, resolution_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    error.error_id,
                    error.category.value,
                    error.severity.value,
                    error.title,
                    error.message,
                    json.dumps(error.context, ensure_ascii=False),
                    error.stack_trace,
                    json.dumps(error.resolution_steps, ensure_ascii=False) if error.resolution_steps else None,
                    error.auto_recovery_attempted,
                    error.resolved,
                    error.resolution_time
                ))
                conn.commit()
            
            # 記錄到應用日誌
            log_message = f"[{error.severity.value.upper()}] {error.category.value}: {error.title} - {error.message}"
            
            if error.severity == ErrorSeverity.CRITICAL:
                self.logger.critical(log_message)
            elif error.severity == ErrorSeverity.HIGH:
                self.logger.error(log_message)
            elif error.severity == ErrorSeverity.MEDIUM:
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)
                
        except Exception as e:
            self.logger.error(f"記錄結構化錯誤失敗: {str(e)}", exc_info=True)
    
    async def suggest_resolution(self, error_type: str) -> List[str]:
        """
        建議解決方案
        
        Args:
            error_type: 錯誤類型
            
        Returns:
            List[str]: 解決步驟列表
        """
        try:
            category = ErrorCategory(error_type.lower())
        except ValueError:
            category = ErrorCategory.UNKNOWN
        
        return self.recovery_strategies.get(category, [
            "檢查錯誤日誌以獲取更多資訊",
            "重試操作",
            "聯繫技術支援"
        ])
    
    async def execute_recovery_action(self, error_id: str, action: RecoveryAction) -> bool:
        """
        執行恢復動作
        
        Args:
            error_id: 錯誤ID
            action: 恢復動作
            
        Returns:
            bool: 執行是否成功
        """
        start_time = time.time()
        success = False
        output = ""
        error_message = ""
        
        try:
            self.logger.info(f"執行恢復動作: {action.action_type} for error {error_id}")
            
            if action.command:
                import subprocess
                
                result = subprocess.run(
                    action.command.split(),
                    capture_output=True,
                    text=True,
                    timeout=action.timeout_seconds,
                    cwd=self.project_root
                )
                
                success = result.returncode == 0
                output = result.stdout
                error_message = result.stderr if not success else ""
            else:
                # 非命令型動作（如檢查、驗證等）
                success = True
                output = f"動作 {action.action_type} 已標記執行"
            
            # 記錄恢復動作結果
            execution_time = int((time.time() - start_time) * 1000)
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute('''
                    INSERT INTO recovery_actions (
                        error_id, action_type, description, command, success,
                        execution_time_ms, output, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    error_id, action.action_type, action.description,
                    action.command, success, execution_time, output, error_message
                ))
                conn.commit()
            
            if success:
                self.logger.info(f"恢復動作執行成功: {action.action_type}")
                # 標記錯誤已解決
                await self._update_error_status(error_id, resolved=True, resolution_time=datetime.now())
            else:
                self.logger.error(f"恢復動作執行失敗: {action.action_type}, 錯誤: {error_message}")
            
            return success
            
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"執行恢復動作異常: {action.action_type}, {str(e)}", exc_info=True)
            
            # 記錄異常結果
            execution_time = int((time.time() - start_time) * 1000)
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute('''
                    INSERT INTO recovery_actions (
                        error_id, action_type, description, command, success,
                        execution_time_ms, output, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    error_id, action.action_type, action.description,
                    action.command, False, execution_time, "", error_message
                ))
                conn.commit()
            
            return False
    
    async def generate_error_report(self, days: int = 7) -> ErrorReport:
        """
        生成錯誤報告
        
        Args:
            days: 報告時間範圍（天）
            
        Returns:
            ErrorReport: 錯誤報告
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 查詢指定時間範圍內的錯誤
                cursor = conn.execute('''
                    SELECT * FROM deployment_errors 
                    WHERE timestamp >= datetime('now', '-{} days')
                    ORDER BY timestamp DESC
                '''.format(days))
                
                errors = []
                for row in cursor.fetchall():
                    error = DeploymentError(
                        error_id=row[1],
                        timestamp=datetime.fromisoformat(row[2]),
                        category=ErrorCategory(row[3]),
                        severity=ErrorSeverity(row[4]),
                        title=row[5],
                        message=row[6],
                        context=json.loads(row[7]) if row[7] else {},
                        stack_trace=row[8],
                        resolution_steps=json.loads(row[9]) if row[9] else None,
                        auto_recovery_attempted=bool(row[10]),
                        resolved=bool(row[11]),
                        resolution_time=datetime.fromisoformat(row[12]) if row[12] else None
                    )
                    errors.append(error)
                
                # 統計分析
                total_errors = len(errors)
                
                error_by_category = {}
                error_by_severity = {}
                resolved_count = 0
                
                for error in errors:
                    # 按分類統計
                    category = error.category.value
                    error_by_category[category] = error_by_category.get(category, 0) + 1
                    
                    # 按嚴重性統計
                    severity = error.severity.value
                    error_by_severity[severity] = error_by_severity.get(severity, 0) + 1
                    
                    # 解決率統計
                    if error.resolved:
                        resolved_count += 1
                
                resolution_success_rate = (resolved_count / total_errors * 100) if total_errors > 0 else 0.0
                
                # 生成建議
                recommendations = self._generate_report_recommendations(errors)
                
                return ErrorReport(
                    timestamp=datetime.now(),
                    total_errors=total_errors,
                    error_by_category=error_by_category,
                    error_by_severity=error_by_severity,
                    recent_errors=errors[:10],  # 最近10個錯誤
                    resolution_success_rate=resolution_success_rate,
                    recommendations=recommendations
                )
                
        except Exception as e:
            self.logger.error(f"生成錯誤報告失敗: {str(e)}", exc_info=True)
            return ErrorReport(
                timestamp=datetime.now(),
                total_errors=0,
                error_by_category={},
                error_by_severity={},
                recent_errors=[],
                resolution_success_rate=0.0,
                recommendations=["無法生成報告，請檢查錯誤資料庫"]
            )
    
    # === 內部方法 ===
    
    def _build_classification_rules(self) -> Dict[str, tuple]:
        """構建錯誤分類規則"""
        return {
            # Docker相關錯誤
            'docker': (ErrorCategory.DOCKER, ErrorSeverity.HIGH),
            'container': (ErrorCategory.DOCKER, ErrorSeverity.HIGH),
            'compose': (ErrorCategory.DOCKER, ErrorSeverity.HIGH),
            'image': (ErrorCategory.DOCKER, ErrorSeverity.MEDIUM),
            
            # 網路相關錯誤
            'connection': (ErrorCategory.NETWORK, ErrorSeverity.MEDIUM),
            'timeout': (ErrorCategory.NETWORK, ErrorSeverity.MEDIUM),
            'network': (ErrorCategory.NETWORK, ErrorSeverity.MEDIUM),
            'port': (ErrorCategory.NETWORK, ErrorSeverity.MEDIUM),
            
            # 權限相關錯誤
            'permission': (ErrorCategory.PERMISSION, ErrorSeverity.HIGH),
            'access': (ErrorCategory.PERMISSION, ErrorSeverity.HIGH),
            'denied': (ErrorCategory.PERMISSION, ErrorSeverity.HIGH),
            
            # 配置相關錯誤
            'config': (ErrorCategory.CONFIGURATION, ErrorSeverity.MEDIUM),
            'yaml': (ErrorCategory.CONFIGURATION, ErrorSeverity.MEDIUM),
            'environment': (ErrorCategory.ENVIRONMENT, ErrorSeverity.MEDIUM),
            
            # 資源相關錯誤
            'memory': (ErrorCategory.RESOURCE, ErrorSeverity.HIGH),
            'disk': (ErrorCategory.RESOURCE, ErrorSeverity.HIGH),
            'space': (ErrorCategory.RESOURCE, ErrorSeverity.HIGH),
            
            # 依賴相關錯誤
            'dependency': (ErrorCategory.DEPENDENCY, ErrorSeverity.MEDIUM),
            'import': (ErrorCategory.DEPENDENCY, ErrorSeverity.MEDIUM),
            'module': (ErrorCategory.DEPENDENCY, ErrorSeverity.MEDIUM),
        }
    
    def _build_recovery_strategies(self) -> Dict[ErrorCategory, List[str]]:
        """構建恢復策略"""
        return {
            ErrorCategory.DOCKER: [
                "檢查Docker服務是否運行",
                "檢查Docker Compose文件語法",
                "清理Docker緩存：docker system prune",
                "重新構建鏡像：docker-compose build --no-cache"
            ],
            ErrorCategory.NETWORK: [
                "檢查網路連接",
                "檢查端口是否被佔用",
                "檢查防火牆設定",
                "重啟網路服務"
            ],
            ErrorCategory.PERMISSION: [
                "檢查文件和目錄權限",
                "確認用戶具有必要權限",
                "使用sudo執行或修改權限",
                "檢查Docker用戶組設定"
            ],
            ErrorCategory.CONFIGURATION: [
                "驗證配置文件語法",
                "檢查環境變數設定",
                "比對參考配置文件",
                "恢復默認配置"
            ],
            ErrorCategory.RESOURCE: [
                "檢查磁盤空間",
                "檢查記憶體使用情況",
                "清理臨時文件",
                "增加系統資源"
            ],
            ErrorCategory.DEPENDENCY: [
                "檢查依賴包是否安裝",
                "更新依賴包版本",
                "重新安裝依賴：pip install -r requirements.txt",
                "檢查Python版本相容性"
            ],
            ErrorCategory.SERVICE: [
                "重啟服務",
                "檢查服務配置",
                "查看服務日誌",
                "檢查服務依賴"
            ],
            ErrorCategory.ENVIRONMENT: [
                "檢查作業系統相容性",
                "檢查環境變數",
                "檢查系統依賴",
                "重新安裝環境"
            ],
        }
    
    def _classify_error(self, error: Exception, context: Dict[str, Any]) -> tuple:
        """分類錯誤"""
        error_text = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # 根據錯誤訊息分類
        for keyword, (category, severity) in self.classification_rules.items():
            if keyword in error_text or keyword in error_type:
                return category, severity
        
        # 根據上下文分類
        if context.get('docker_command'):
            return ErrorCategory.DOCKER, ErrorSeverity.HIGH
        elif context.get('network_operation'):
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        elif context.get('file_operation'):
            return ErrorCategory.PERMISSION, ErrorSeverity.MEDIUM
        
        # 默認分類
        return ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM
    
    def _generate_error_id(self, error: Exception, context: Dict[str, Any]) -> str:
        """生成錯誤ID"""
        import hashlib
        
        # 組合錯誤特徵
        error_signature = f"{type(error).__name__}:{str(error)[:100]}:{context.get('operation', 'unknown')}"
        
        # 生成短ID
        hash_object = hashlib.md5(error_signature.encode())
        return f"E-{hash_object.hexdigest()[:8]}"
    
    def _extract_error_title(self, error: Exception) -> str:
        """提取錯誤標題"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        # 簡化錯誤訊息作為標題
        if len(error_msg) > 60:
            return f"{error_type}: {error_msg[:60]}..."
        else:
            return f"{error_type}: {error_msg}"
    
    def _generate_resolution_steps(self, error: Exception, context: Dict[str, Any], 
                                 category: ErrorCategory) -> List[str]:
        """生成解決步驟"""
        base_steps = self.recovery_strategies.get(category, [])
        
        # 根據具體錯誤類型添加特定步驟
        specific_steps = []
        error_msg = str(error).lower()
        
        if 'not found' in error_msg:
            specific_steps.append("檢查文件或命令是否存在")
        elif 'connection refused' in error_msg:
            specific_steps.append("檢查目標服務是否運行並可訪問")
        elif 'permission denied' in error_msg:
            specific_steps.append("檢查權限設定並嘗試使用管理員權限")
        
        return specific_steps + base_steps
    
    def _suggest_recovery_action(self, error: DeploymentError) -> RecoveryAction:
        """建議恢復動作"""
        category = error.category
        severity = error.severity
        
        # 根據錯誤類型決定恢復動作
        if category == ErrorCategory.DOCKER:
            if 'compose' in error.message.lower():
                return RecoveryAction(
                    action_type="restart_compose",
                    description="重啟Docker Compose服務",
                    command="docker-compose restart",
                    timeout_seconds=60
                )
            else:
                return RecoveryAction(
                    action_type="restart_docker",
                    description="重啟Docker服務",
                    timeout_seconds=30
                )
        
        elif category == ErrorCategory.NETWORK:
            return RecoveryAction(
                action_type="check_network",
                description="檢查網路連接和端口",
                timeout_seconds=15
            )
        
        elif category == ErrorCategory.PERMISSION:
            return RecoveryAction(
                action_type="fix_permissions",
                description="修復權限問題",
                command="chmod -R 755 .",
                timeout_seconds=30
            )
        
        elif category == ErrorCategory.RESOURCE:
            return RecoveryAction(
                action_type="clean_resources",
                description="清理系統資源",
                command="docker system prune -f",
                timeout_seconds=120
            )
        
        else:
            return RecoveryAction(
                action_type="manual_check",
                description="需要手動檢查和處理",
                timeout_seconds=0
            )
    
    def _is_auto_recoverable(self, category: ErrorCategory, severity: ErrorSeverity) -> bool:
        """判斷是否可自動恢復"""
        # 低嚴重性的網路、配置和依賴問題可以嘗試自動恢復
        if severity == ErrorSeverity.LOW:
            return True
        elif severity == ErrorSeverity.MEDIUM and category in [
            ErrorCategory.NETWORK, ErrorCategory.CONFIGURATION, ErrorCategory.DEPENDENCY
        ]:
            return True
        else:
            return False
    
    async def _update_error_status(self, error_id: str, resolved: bool = None, 
                                 resolution_time: datetime = None, 
                                 auto_recovery_attempted: bool = None) -> None:
        """更新錯誤狀態"""
        try:
            updates = []
            values = []
            
            if resolved is not None:
                updates.append("resolved = ?")
                values.append(resolved)
            
            if resolution_time is not None:
                updates.append("resolution_time = ?")
                values.append(resolution_time)
            
            if auto_recovery_attempted is not None:
                updates.append("auto_recovery_attempted = ?")
                values.append(auto_recovery_attempted)
            
            if updates:
                values.append(error_id)
                with sqlite3.connect(str(self.db_path)) as conn:
                    conn.execute(f'''
                        UPDATE deployment_errors 
                        SET {', '.join(updates)}
                        WHERE error_id = ?
                    ''', values)
                    conn.commit()
                    
        except Exception as e:
            self.logger.error(f"更新錯誤狀態失敗: {str(e)}")
    
    def _generate_report_recommendations(self, errors: List[DeploymentError]) -> List[str]:
        """生成報告建議"""
        recommendations = []
        
        # 分析錯誤模式
        docker_errors = [e for e in errors if e.category == ErrorCategory.DOCKER]
        network_errors = [e for e in errors if e.category == ErrorCategory.NETWORK]
        config_errors = [e for e in errors if e.category == ErrorCategory.CONFIGURATION]
        
        if len(docker_errors) > len(errors) * 0.3:
            recommendations.append("Docker相關錯誤較多，建議檢查Docker環境配置")
        
        if len(network_errors) > len(errors) * 0.2:
            recommendations.append("網路錯誤頻繁，建議檢查網路設定和防火牆")
        
        if len(config_errors) > len(errors) * 0.2:
            recommendations.append("配置錯誤較多，建議審查配置文件和環境變數")
        
        # 檢查未解決的關鍵錯誤
        critical_unresolved = [e for e in errors 
                             if e.severity == ErrorSeverity.CRITICAL and not e.resolved]
        if critical_unresolved:
            recommendations.append(f"存在{len(critical_unresolved)}個未解決的關鍵錯誤，需要優先處理")
        
        # 自動恢復建議
        auto_recovery_failed = [e for e in errors 
                              if e.auto_recovery_attempted and not e.resolved]
        if len(auto_recovery_failed) > 5:
            recommendations.append("自動恢復失敗率較高，建議改進錯誤恢復策略")
        
        return recommendations or ["系統運行穩定，無特殊建議"]


# 工具函數和裝飾器

def error_boundary(error_handler: ErrorHandler):
    """錯誤邊界裝飾器"""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                }
                recovery_action = await error_handler.handle_error(e, context)
                raise DeploymentError(
                    error_id=f"BOUNDARY-{int(time.time())}",
                    timestamp=datetime.now(),
                    category=ErrorCategory.UNKNOWN,
                    severity=ErrorSeverity.HIGH,
                    title=f"函數 {func.__name__} 執行失敗",
                    message=str(e),
                    context=context
                ) from e
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                }
                # 同步函數只能記錄錯誤，不能執行異步恢復
                logger.error(f"錯誤邊界捕獲錯誤: {func.__name__}: {str(e)}")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# 命令行介面
async def main():
    """主函數 - 用於獨立執行錯誤處理工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 錯誤處理工具')
    parser.add_argument('command', choices=['report', 'resolve', 'test'],
                       help='執行的命令')
    parser.add_argument('--error-id', help='指定錯誤ID（用於resolve命令）')
    parser.add_argument('--days', type=int, default=7, help='報告時間範圍（天）')
    parser.add_argument('--output', '-o', help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 創建錯誤處理器
    error_handler = ErrorHandler()
    
    try:
        if args.command == 'report':
            report = await error_handler.generate_error_report(args.days)
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(asdict(report), f, indent=2, ensure_ascii=False, default=str)
                print(f"錯誤報告已保存到: {args.output}")
            else:
                print(f"\n{'='*60}")
                print("🔍 ROAS Bot v2.4.3 錯誤報告")
                print(f"{'='*60}")
                print(f"報告時間: {report.timestamp}")
                print(f"總錯誤數: {report.total_errors}")
                print(f"解決成功率: {report.resolution_success_rate:.1f}%")
                
                if report.error_by_category:
                    print(f"\n錯誤分類統計:")
                    for category, count in report.error_by_category.items():
                        print(f"  {category}: {count}")
                
                if report.error_by_severity:
                    print(f"\n錯誤嚴重性統計:")
                    for severity, count in report.error_by_severity.items():
                        print(f"  {severity}: {count}")
                
                if report.recent_errors:
                    print(f"\n最近錯誤:")
                    for error in report.recent_errors[:5]:
                        print(f"  • [{error.severity.value}] {error.title}")
                
                if report.recommendations:
                    print(f"\n💡 建議:")
                    for rec in report.recommendations:
                        print(f"  • {rec}")
            
            return 0
            
        elif args.command == 'test':
            # 測試錯誤處理功能
            try:
                raise ValueError("這是一個測試錯誤")
            except Exception as e:
                context = {'operation': 'test', 'component': 'error_handler'}
                recovery_action = await error_handler.handle_error(e, context)
                print(f"測試錯誤已處理，建議動作: {recovery_action.action_type}")
            
            return 0
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        return 1


if __name__ == '__main__':
    import sys
    import asyncio
    sys.exit(asyncio.run(main()))