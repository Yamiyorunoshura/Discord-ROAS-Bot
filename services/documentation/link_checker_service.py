"""
連結檢查服務實作
Task ID: T3 - 文檔連結有效性修復

提供程式化的文檔連結檢查API服務，整合到主系統服務框架
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor

from .link_checker import LinkChecker
from .link_checker_models import (
    CheckResult, LinkCheckConfig, PeriodicCheckSchedule, 
    LinkCheckHistory, ValidationReport, LinkStatus
)

logger = logging.getLogger('services.documentation.link_checker_service')


class LinkCheckerService:
    """
    文檔連結檢查服務
    
    提供程式化的連結檢查API介面，支援：
    - 按需連結檢查
    - 定期自動檢查
    - 檢查歷史管理
    - 錯誤通知機制
    - 多種報告格式
    """
    
    def __init__(self, 
                 base_path: str,
                 config: Optional[LinkCheckConfig] = None,
                 notification_callback: Optional[Callable] = None):
        """
        初始化連結檢查服務
        
        參數:
            base_path: 文檔基礎路徑
            config: 連結檢查配置
            notification_callback: 錯誤通知回呼函數
        """
        self.base_path = Path(base_path)
        self.config = config or LinkCheckConfig(base_path=str(base_path))
        self.notification_callback = notification_callback
        
        # 初始化連結檢查器
        self.link_checker = LinkChecker(self.config)
        
        # 服務狀態
        self._initialized = False
        self._running_checks: Dict[str, asyncio.Task] = {}
        self._periodic_schedules: Dict[str, PeriodicCheckSchedule] = {}
        self._check_history: List[LinkCheckHistory] = []
        self._scheduler_task: Optional[asyncio.Task] = None
        self._shutdown = False
        
        # 線程池用於並發檢查
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # 報告儲存路徑
        self.reports_path = self.base_path / "docs" / "reports" / "link_checks"
        self.reports_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"連結檢查服務初始化 - 基礎路徑: {self.base_path}")
    
    async def initialize(self) -> None:
        """初始化服務"""
        if self._initialized:
            return
        
        try:
            # 載入已保存的排程
            await self._load_schedules()
            
            # 啟動定期檢查排程器
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            
            self._initialized = True
            logger.info("連結檢查服務初始化完成")
            
        except Exception as e:
            logger.error(f"初始化連結檢查服務失敗: {e}")
            raise
    
    async def shutdown(self) -> None:
        """關閉服務"""
        logger.info("正在關閉連結檢查服務...")
        self._shutdown = True
        
        # 停止排程器
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有運行中的檢查
        for check_id, task in self._running_checks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug(f"已取消檢查任務: {check_id}")
        
        # 關閉連結檢查器
        await self.link_checker.close()
        
        # 關閉線程池
        self.executor.shutdown(wait=True)
        
        self._initialized = False
        logger.info("連結檢查服務已關閉")
    
    async def check_documentation(
        self, 
        target_paths: Optional[List[str]] = None,
        config_override: Optional[LinkCheckConfig] = None
    ) -> CheckResult:
        """
        檢查文檔連結有效性
        
        參數:
            target_paths: 目標路徑列表，None表示檢查所有文檔
            config_override: 臨時配置覆蓋
            
        返回:
            CheckResult: 檢查結果
        """
        if not self._initialized:
            await self.initialize()
        
        check_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"開始文檔連結檢查 - ID: {check_id}")
        
        try:
            # 使用覆蓋配置或預設配置
            check_config = config_override or self.config
            checker = LinkChecker(check_config)
            
            # 確定檢查路徑
            if target_paths is None:
                target_paths = [str(self.base_path / "docs")]
            
            # 掃描所有文檔
            all_documents = []
            for path in target_paths:
                documents = checker.scan_directory(path)
                all_documents.extend(documents)
            
            if not all_documents:
                logger.warning("沒有找到要檢查的文檔")
                return CheckResult(
                    check_id=check_id,
                    timestamp=datetime.now(),
                    documents_checked=0,
                    total_links_found=0,
                    valid_links=0,
                    broken_links=0,
                    check_duration_ms=0.0,
                    reports=[],
                    summary={"status": "no_documents", "message": "沒有找到文檔"},
                    configuration=self._config_to_dict(check_config)
                )
            
            # 驗證連結
            report = await checker.validate_links(all_documents)
            
            # 計算統計資料
            total_links = report.total_links
            valid_links = report.valid_links
            broken_links = report.invalid_links
            
            # 建立檢查結果
            duration_ms = (time.time() - start_time) * 1000
            
            check_result = CheckResult(
                check_id=check_id,
                timestamp=datetime.now(),
                documents_checked=len(all_documents),
                total_links_found=total_links,
                valid_links=valid_links,
                broken_links=broken_links,
                check_duration_ms=duration_ms,
                reports=[report],
                summary=self._create_summary(report, all_documents),
                configuration=self._config_to_dict(check_config)
            )
            
            # 保存檢查結果
            await self._save_check_result(check_result)
            
            # 發送通知（如果有問題）
            if check_result.has_failures and self.notification_callback:
                await self._send_notification(check_result)
            
            logger.info(
                f"文檔連結檢查完成 - ID: {check_id}, "
                f"耗時: {duration_ms:.0f}ms, "
                f"有效率: {check_result.overall_success_rate:.1f}%"
            )
            
            return check_result
            
        except Exception as e:
            error_msg = f"文檔連結檢查失敗: {e}"
            logger.exception(error_msg)
            
            return CheckResult(
                check_id=check_id,
                timestamp=datetime.now(),
                documents_checked=0,
                total_links_found=0,
                valid_links=0,
                broken_links=0,
                check_duration_ms=(time.time() - start_time) * 1000,
                reports=[],
                summary={"status": "error", "message": error_msg},
                configuration=self._config_to_dict(self.config)
            )
        
        finally:
            await checker.close()
    
    def schedule_periodic_check(
        self, 
        interval_hours: int,
        name: str = "default",
        target_directories: Optional[List[str]] = None,
        config_override: Optional[LinkCheckConfig] = None
    ) -> str:
        """
        安排定期自動檢查
        
        參數:
            interval_hours: 檢查間隔（小時）
            name: 排程名稱
            target_directories: 目標目錄列表
            config_override: 配置覆蓋
            
        返回:
            schedule_id: 排程ID
        """
        schedule_id = f"schedule_{name}_{int(time.time())}"
        
        if target_directories is None:
            target_directories = [str(self.base_path / "docs")]
        
        schedule = PeriodicCheckSchedule(
            schedule_id=schedule_id,
            name=name,
            interval_hours=interval_hours,
            next_check_time=datetime.now() + timedelta(hours=interval_hours),
            target_directories=target_directories,
            config=config_override or self.config,
            enabled=True
        )
        
        self._periodic_schedules[schedule_id] = schedule
        
        # 保存排程
        asyncio.create_task(self._save_schedules())
        
        logger.info(f"已創建定期檢查排程 - ID: {schedule_id}, 間隔: {interval_hours}小時")
        return schedule_id
    
    def cancel_periodic_check(self, schedule_id: str) -> bool:
        """
        取消定期檢查
        
        參數:
            schedule_id: 排程ID
            
        返回:
            是否取消成功
        """
        if schedule_id in self._periodic_schedules:
            self._periodic_schedules[schedule_id].enabled = False
            asyncio.create_task(self._save_schedules())
            logger.info(f"已取消定期檢查排程: {schedule_id}")
            return True
        return False
    
    def get_check_history(
        self, 
        limit: int = 10,
        since_days: Optional[int] = None
    ) -> List[CheckResult]:
        """
        獲取檢查歷史
        
        參數:
            limit: 返回結果數量限制
            since_days: 只返回最近N天的結果
            
        返回:
            檢查結果列表
        """
        results = []
        cutoff_date = None
        
        if since_days:
            cutoff_date = datetime.now() - timedelta(days=since_days)
        
        # 過濾並排序歷史記錄
        filtered_history = []
        for history in self._check_history:
            if cutoff_date and history.check_result.timestamp < cutoff_date:
                continue
            filtered_history.append(history.check_result)
        
        # 按時間戳排序（最新在前）
        filtered_history.sort(key=lambda x: x.timestamp, reverse=True)
        
        return filtered_history[:limit]
    
    def get_periodic_schedules(self) -> List[PeriodicCheckSchedule]:
        """獲取所有定期檢查排程"""
        return list(self._periodic_schedules.values())
    
    async def get_service_status(self) -> Dict[str, Any]:
        """
        獲取服務狀態
        
        返回:
            服務狀態資訊
        """
        return {
            "initialized": self._initialized,
            "base_path": str(self.base_path),
            "running_checks": len(self._running_checks),
            "periodic_schedules": len(self._periodic_schedules),
            "active_schedules": len([s for s in self._periodic_schedules.values() if s.enabled]),
            "history_count": len(self._check_history),
            "cache_stats": self.link_checker.get_cache_stats() if self._initialized else {},
            "last_cleanup": self._last_cleanup.isoformat() if hasattr(self, '_last_cleanup') else None
        }
    
    async def export_report(
        self, 
        check_result: CheckResult, 
        format: str = "markdown"
    ) -> str:
        """
        匯出檢查報告
        
        參數:
            check_result: 檢查結果
            format: 報告格式 ("markdown", "json", "csv", "text")
            
        返回:
            報告文件路徑
        """
        if not check_result.reports:
            raise ValueError("檢查結果中沒有報告資料")
        
        report = check_result.reports[0]  # 使用第一個報告
        
        # 生成報告內容
        checker = LinkChecker(self.config)
        report_content = checker.generate_report(report, format)
        
        # 確定檔案名稱
        timestamp = check_result.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"link_check_report_{check_result.check_id}_{timestamp}.{format}"
        file_path = self.reports_path / filename
        
        # 寫入檔案
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"報告已匯出: {file_path}")
        return str(file_path)
    
    async def cleanup_old_reports(self, keep_days: int = 7) -> int:
        """
        清理舊報告檔案
        
        參數:
            keep_days: 保留天數
            
        返回:
            清理的檔案數量
        """
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        cleaned_count = 0
        
        if not self.reports_path.exists():
            return 0
        
        for file_path in self.reports_path.iterdir():
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.debug(f"已清理舊報告: {file_path}")
                    except Exception as e:
                        logger.error(f"清理報告檔案失敗 {file_path}: {e}")
        
        # 清理過期的檢查歷史
        original_count = len(self._check_history)
        self._check_history = [
            h for h in self._check_history
            if h.archived_at > cutoff_date
        ]
        
        self._last_cleanup = datetime.now()
        logger.info(f"清理完成 - 檔案: {cleaned_count}, 歷史記錄: {original_count - len(self._check_history)}")
        
        return cleaned_count
    
    async def _scheduler_loop(self):
        """定期檢查排程循環"""
        logger.info("定期檢查排程器已啟動")
        
        while not self._shutdown:
            try:
                await asyncio.sleep(60)  # 每分鐘檢查一次
                
                current_time = datetime.now()
                
                for schedule_id, schedule in list(self._periodic_schedules.items()):
                    if not schedule.enabled:
                        continue
                    
                    if current_time >= schedule.next_check_time:
                        logger.info(f"觸發定期檢查: {schedule.name}")
                        
                        # 啟動檢查任務
                        task = asyncio.create_task(
                            self._run_scheduled_check(schedule)
                        )
                        self._running_checks[f"scheduled_{schedule_id}"] = task
                        
                        # 更新下次檢查時間
                        schedule.next_check_time = current_time + timedelta(
                            hours=schedule.interval_hours
                        )
                        schedule.last_check_time = current_time
                
                # 清理完成的任務
                completed_checks = [
                    check_id for check_id, task in self._running_checks.items()
                    if task.done()
                ]
                for check_id in completed_checks:
                    del self._running_checks[check_id]
                
            except Exception as e:
                logger.error(f"排程器循環錯誤: {e}")
    
    async def _run_scheduled_check(self, schedule: PeriodicCheckSchedule):
        """執行排程的檢查"""
        try:
            result = await self.check_documentation(
                target_paths=schedule.target_directories,
                config_override=schedule.config
            )
            
            schedule.last_result_id = result.check_id
            
            logger.info(f"定期檢查完成: {schedule.name}, 結果: {result.check_id}")
            
        except Exception as e:
            logger.error(f"定期檢查失敗: {schedule.name}, 錯誤: {e}")
    
    async def _save_check_result(self, result: CheckResult):
        """保存檢查結果"""
        # 加入歷史記錄
        history = LinkCheckHistory(
            history_id=f"history_{result.check_id}",
            check_result=result,
            archived_at=datetime.now()
        )
        
        self._check_history.append(history)
        
        # 限制歷史記錄數量
        if len(self._check_history) > 50:
            self._check_history = self._check_history[-50:]
        
        # 保存到檔案
        try:
            result_file = self.reports_path / f"result_{result.check_id}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                # 轉換為可序列化的格式
                serializable_result = self._result_to_dict(result)
                json.dump(serializable_result, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"檢查結果已保存: {result_file}")
            
        except Exception as e:
            logger.error(f"保存檢查結果失敗: {e}")
    
    async def _send_notification(self, result: CheckResult):
        """發送通知"""
        if not self.notification_callback:
            return
        
        try:
            notification_data = {
                "type": "link_check_failure",
                "check_id": result.check_id,
                "timestamp": result.timestamp.isoformat(),
                "broken_links_count": result.broken_links,
                "success_rate": result.overall_success_rate,
                "summary": result.summary
            }
            
            await self.notification_callback(notification_data)
            
        except Exception as e:
            logger.error(f"發送通知失敗: {e}")
    
    async def _load_schedules(self):
        """載入已保存的排程"""
        schedules_file = self.reports_path / "schedules.json"
        
        if not schedules_file.exists():
            return
        
        try:
            with open(schedules_file, 'r', encoding='utf-8') as f:
                schedules_data = json.load(f)
            
            for schedule_data in schedules_data:
                schedule = PeriodicCheckSchedule(
                    schedule_id=schedule_data['schedule_id'],
                    name=schedule_data['name'],
                    interval_hours=schedule_data['interval_hours'],
                    next_check_time=datetime.fromisoformat(schedule_data['next_check_time']),
                    target_directories=schedule_data['target_directories'],
                    config=LinkCheckConfig(**schedule_data['config']),
                    enabled=schedule_data.get('enabled', True),
                    last_check_time=datetime.fromisoformat(schedule_data['last_check_time']) 
                                    if schedule_data.get('last_check_time') else None,
                    last_result_id=schedule_data.get('last_result_id')
                )
                
                self._periodic_schedules[schedule.schedule_id] = schedule
            
            logger.info(f"載入了 {len(self._periodic_schedules)} 個定期檢查排程")
            
        except Exception as e:
            logger.error(f"載入排程失敗: {e}")
    
    async def _save_schedules(self):
        """保存排程到檔案"""
        schedules_file = self.reports_path / "schedules.json"
        
        try:
            schedules_data = []
            for schedule in self._periodic_schedules.values():
                schedule_dict = {
                    'schedule_id': schedule.schedule_id,
                    'name': schedule.name,
                    'interval_hours': schedule.interval_hours,
                    'next_check_time': schedule.next_check_time.isoformat(),
                    'target_directories': schedule.target_directories,
                    'config': {
                        'check_external_links': schedule.config.check_external_links,
                        'check_anchors': schedule.config.check_anchors,
                        'timeout_seconds': schedule.config.timeout_seconds,
                        'ignore_patterns': schedule.config.ignore_patterns,
                        'file_extensions': schedule.config.file_extensions
                    },
                    'enabled': schedule.enabled,
                    'last_check_time': schedule.last_check_time.isoformat() 
                                     if schedule.last_check_time else None,
                    'last_result_id': schedule.last_result_id
                }
                schedules_data.append(schedule_dict)
            
            with open(schedules_file, 'w', encoding='utf-8') as f:
                json.dump(schedules_data, f, indent=2, ensure_ascii=False)
            
            logger.debug("排程已保存")
            
        except Exception as e:
            logger.error(f"保存排程失敗: {e}")
    
    def _config_to_dict(self, config: LinkCheckConfig) -> Dict[str, Any]:
        """將配置轉換為字典"""
        return {
            "check_external_links": config.check_external_links,
            "check_anchors": config.check_anchors,
            "follow_redirects": config.follow_redirects,
            "timeout_seconds": config.timeout_seconds,
            "max_concurrent_checks": config.max_concurrent_checks,
            "ignore_patterns": config.ignore_patterns,
            "base_path": config.base_path,
            "file_extensions": config.file_extensions
        }
    
    def _result_to_dict(self, result: CheckResult) -> Dict[str, Any]:
        """將檢查結果轉換為可序列化的字典"""
        return {
            "check_id": result.check_id,
            "timestamp": result.timestamp.isoformat(),
            "documents_checked": result.documents_checked,
            "total_links_found": result.total_links_found,
            "valid_links": result.valid_links,
            "broken_links": result.broken_links,
            "check_duration_ms": result.check_duration_ms,
            "overall_success_rate": result.overall_success_rate,
            "has_failures": result.has_failures,
            "summary": result.summary,
            "configuration": result.configuration
        }
    
    def _create_summary(self, report: ValidationReport, documents: List) -> Dict[str, Any]:
        """建立檢查結果摘要"""
        return {
            "status": "completed",
            "documents_scanned": len(documents),
            "success_rate": report.success_rate,
            "issues_found": len(report.broken_links),
            "warnings_count": len(report.warnings),
            "errors_count": len(report.errors),
            "recommendations": self._generate_recommendations(report)
        }
    
    def _generate_recommendations(self, report: ValidationReport) -> List[str]:
        """生成修復建議"""
        recommendations = []
        
        if report.broken_links:
            recommendations.append(f"修復 {len(report.broken_links)} 個無效連結")
        
        if report.warnings:
            recommendations.append("檢查警告信息並進行相應調整")
        
        if report.success_rate < 90:
            recommendations.append("檢查文檔結構和連結格式的一致性")
        
        if not recommendations:
            recommendations.append("所有連結均有效，文檔品質良好")
        
        return recommendations