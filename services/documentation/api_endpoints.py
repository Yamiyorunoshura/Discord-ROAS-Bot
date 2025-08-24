"""
文檔連結檢查RESTful API端點
Task ID: T3 - 文檔連結有效性修復

提供標準化的REST API介面，整合連結檢查服務
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from .link_checker_service import LinkCheckerService
from .link_checker_models import LinkCheckConfig, CheckResult
from .api_cache_and_error import (
    ResponseCache, ErrorHandler, CachePolicy, 
    cached_api_call, APIError, ErrorSeverity
)

logger = logging.getLogger('services.documentation.api_endpoints')


class LinkCheckAPI:
    """
    文檔連結檢查REST API控制器
    
    提供標準化的RESTful API端點，支援：
    - 文檔連結檢查
    - 定期檢查排程管理
    - 檢查歷史查詢
    - 服務狀態監控
    - 報告匯出
    """
    
    def __init__(self, base_path: str):
        """
        初始化API控制器
        
        參數:
            base_path: 文檔基礎路徑
        """
        self.base_path = base_path
        
        # 初始化服務組件
        self.link_service = LinkCheckerService(base_path)
        self.cache = ResponseCache(max_size=500, default_ttl_seconds=1800)
        self.error_handler = ErrorHandler()
        
        # API配置
        self.api_version = "v1"
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        
        logger.info(f"LinkCheckAPI初始化 - 基礎路徑: {base_path}")
    
    async def initialize(self) -> Dict[str, Any]:
        """
        初始化API服務
        
        返回:
            初始化結果
        """
        try:
            await self.link_service.initialize()
            await self.cache.start()
            
            logger.info("LinkCheckAPI服務初始化成功")
            return self._success_response({
                "message": "API服務初始化成功",
                "version": self.api_version,
                "base_path": self.base_path
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "initialize"}
            )
            return self.error_handler.format_error_response(error)
    
    async def shutdown(self) -> Dict[str, Any]:
        """關閉API服務"""
        try:
            await self.link_service.shutdown()
            await self.cache.stop()
            
            logger.info("LinkCheckAPI服務已關閉")
            return self._success_response({"message": "API服務已關閉"})
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "shutdown"}
            )
            return self.error_handler.format_error_response(error)
    
    @cached_api_call(cache=None, policy=CachePolicy.SHORT_TERM)  # 將在__post_init__中設置
    async def check_links(self, 
                         target_paths: Optional[List[str]] = None,
                         check_external: bool = False,
                         check_anchors: bool = True,
                         output_format: str = "json") -> Dict[str, Any]:
        """
        檢查文檔連結
        
        參數:
            target_paths: 目標路徑列表
            check_external: 是否檢查外部連結
            check_anchors: 是否檢查錨點連結
            output_format: 輸出格式 ("json", "summary")
            
        返回:
            檢查結果
        """
        try:
            # 驗證輸入參數
            validation_error = self._validate_check_params(
                target_paths, check_external, check_anchors, output_format
            )
            if validation_error:
                return validation_error
            
            # 創建檢查配置
            config = LinkCheckConfig(
                check_external_links=check_external,
                check_anchors=check_anchors,
                base_path=self.base_path
            )
            
            # 執行連結檢查
            result = await self.link_service.check_documentation(
                target_paths=target_paths,
                config_override=config
            )
            
            # 格式化響應
            if output_format == "summary":
                response_data = self._format_summary_response(result)
            else:
                response_data = self._format_detailed_response(result)
            
            logger.info(f"連結檢查完成 - ID: {result.check_id}")
            return self._success_response(response_data)
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {
                    "operation": "check_links",
                    "target_paths": target_paths,
                    "check_external": check_external
                }
            )
            return self.error_handler.format_error_response(error)
    
    async def get_check_result(self, check_id: str) -> Dict[str, Any]:
        """
        獲取指定檢查結果
        
        參數:
            check_id: 檢查ID
            
        返回:
            檢查結果詳情
        """
        try:
            # 從歷史記錄中搜尋
            history = self.link_service.get_check_history(limit=100)
            
            result = next((h for h in history if h.check_id == check_id), None)
            
            if not result:
                error = self.error_handler.create_error(
                    "LINK_CHECK_001",
                    {"check_id": check_id},
                    f"找不到檢查ID: {check_id}"
                )
                return self.error_handler.format_error_response(error)
            
            response_data = self._format_detailed_response(result)
            return self._success_response(response_data)
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "get_check_result", "check_id": check_id}
            )
            return self.error_handler.format_error_response(error)
    
    async def list_check_history(self, 
                                limit: int = 10,
                                since_days: Optional[int] = None) -> Dict[str, Any]:
        """
        列出檢查歷史
        
        參數:
            limit: 返回數量限制
            since_days: 只返回最近N天的記錄
            
        返回:
            檢查歷史列表
        """
        try:
            # 驗證參數
            if limit < 1 or limit > 100:
                error = self.error_handler.create_error(
                    "LINK_CHECK_004",
                    {"limit": limit},
                    "limit參數必須在1-100之間"
                )
                return self.error_handler.format_error_response(error)
            
            history = self.link_service.get_check_history(
                limit=limit, 
                since_days=since_days
            )
            
            # 格式化歷史列表
            history_list = []
            for result in history:
                history_list.append({
                    "check_id": result.check_id,
                    "timestamp": result.timestamp.isoformat(),
                    "documents_checked": result.documents_checked,
                    "total_links": result.total_links_found,
                    "success_rate": result.overall_success_rate,
                    "has_failures": result.has_failures,
                    "duration_ms": result.check_duration_ms
                })
            
            return self._success_response({
                "history": history_list,
                "total_count": len(history_list),
                "limit": limit,
                "since_days": since_days
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "list_check_history", "limit": limit}
            )
            return self.error_handler.format_error_response(error)
    
    async def create_periodic_schedule(self,
                                     name: str,
                                     interval_hours: int,
                                     target_directories: Optional[List[str]] = None,
                                     config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        創建定期檢查排程
        
        參數:
            name: 排程名稱
            interval_hours: 檢查間隔（小時）
            target_directories: 目標目錄列表
            config: 檢查配置
            
        返回:
            創建的排程資訊
        """
        try:
            # 驗證參數
            if not name or not name.strip():
                error = self.error_handler.create_error(
                    "LINK_CHECK_004",
                    {"name": name},
                    "排程名稱不能為空"
                )
                return self.error_handler.format_error_response(error)
            
            if interval_hours < 1 or interval_hours > 168:  # 最多1週
                error = self.error_handler.create_error(
                    "LINK_CHECK_004", 
                    {"interval_hours": interval_hours},
                    "檢查間隔必須在1-168小時之間"
                )
                return self.error_handler.format_error_response(error)
            
            # 創建配置
            check_config = None
            if config:
                check_config = LinkCheckConfig(
                    check_external_links=config.get("check_external_links", False),
                    check_anchors=config.get("check_anchors", True),
                    timeout_seconds=config.get("timeout_seconds", 10),
                    ignore_patterns=config.get("ignore_patterns", []),
                    base_path=self.base_path
                )
            
            # 創建排程
            schedule_id = self.link_service.schedule_periodic_check(
                interval_hours=interval_hours,
                name=name,
                target_directories=target_directories,
                config_override=check_config
            )
            
            return self._success_response({
                "schedule_id": schedule_id,
                "name": name,
                "interval_hours": interval_hours,
                "target_directories": target_directories or [f"{self.base_path}/docs"],
                "created_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {
                    "operation": "create_periodic_schedule",
                    "name": name,
                    "interval_hours": interval_hours
                }
            )
            return self.error_handler.format_error_response(error)
    
    async def list_schedules(self) -> Dict[str, Any]:
        """列出所有定期檢查排程"""
        try:
            schedules = self.link_service.get_periodic_schedules()
            
            schedules_list = []
            for schedule in schedules:
                schedules_list.append({
                    "schedule_id": schedule.schedule_id,
                    "name": schedule.name,
                    "interval_hours": schedule.interval_hours,
                    "next_check_time": schedule.next_check_time.isoformat(),
                    "target_directories": schedule.target_directories,
                    "enabled": schedule.enabled,
                    "last_check_time": schedule.last_check_time.isoformat() 
                                     if schedule.last_check_time else None,
                    "last_result_id": schedule.last_result_id
                })
            
            return self._success_response({
                "schedules": schedules_list,
                "total_count": len(schedules_list)
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "list_schedules"}
            )
            return self.error_handler.format_error_response(error)
    
    async def cancel_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """
        取消定期檢查排程
        
        參數:
            schedule_id: 排程ID
            
        返回:
            取消結果
        """
        try:
            success = self.link_service.cancel_periodic_check(schedule_id)
            
            if not success:
                error = self.error_handler.create_error(
                    "LINK_CHECK_001",
                    {"schedule_id": schedule_id},
                    f"找不到排程: {schedule_id}"
                )
                return self.error_handler.format_error_response(error)
            
            return self._success_response({
                "schedule_id": schedule_id,
                "status": "cancelled",
                "cancelled_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "cancel_schedule", "schedule_id": schedule_id}
            )
            return self.error_handler.format_error_response(error)
    
    async def export_report(self,
                           check_id: str,
                           format: str = "markdown") -> Dict[str, Any]:
        """
        匯出檢查報告
        
        參數:
            check_id: 檢查ID
            format: 報告格式 ("markdown", "json", "csv", "text")
            
        返回:
            報告檔案資訊
        """
        try:
            # 驗證格式
            valid_formats = ["markdown", "json", "csv", "text"]
            if format not in valid_formats:
                error = self.error_handler.create_error(
                    "LINK_CHECK_004",
                    {"format": format, "valid_formats": valid_formats},
                    f"不支援的格式: {format}"
                )
                return self.error_handler.format_error_response(error)
            
            # 獲取檢查結果
            history = self.link_service.get_check_history(limit=100)
            result = next((h for h in history if h.check_id == check_id), None)
            
            if not result:
                error = self.error_handler.create_error(
                    "LINK_CHECK_001",
                    {"check_id": check_id},
                    f"找不到檢查結果: {check_id}"
                )
                return self.error_handler.format_error_response(error)
            
            # 匯出報告
            report_path = await self.link_service.export_report(result, format)
            
            return self._success_response({
                "check_id": check_id,
                "format": format,
                "report_path": report_path,
                "file_size": Path(report_path).stat().st_size,
                "exported_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {
                    "operation": "export_report",
                    "check_id": check_id,
                    "format": format
                }
            )
            return self.error_handler.format_error_response(error)
    
    async def get_service_status(self) -> Dict[str, Any]:
        """獲取服務狀態"""
        try:
            # 獲取服務狀態
            service_status = await self.link_service.get_service_status()
            
            # 獲取快取統計
            cache_stats = self.cache.get_stats()
            
            # 獲取錯誤統計
            error_stats = self.error_handler.get_error_statistics()
            
            return self._success_response({
                "service": service_status,
                "cache": cache_stats,
                "errors": error_stats,
                "api_version": self.api_version,
                "uptime": service_status.get("uptime", "unknown")
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "get_service_status"}
            )
            return self.error_handler.format_error_response(error)
    
    async def cleanup_reports(self, keep_days: int = 7) -> Dict[str, Any]:
        """
        清理舊報告
        
        參數:
            keep_days: 保留天數
            
        返回:
            清理結果
        """
        try:
            if keep_days < 1 or keep_days > 365:
                error = self.error_handler.create_error(
                    "LINK_CHECK_004",
                    {"keep_days": keep_days},
                    "保留天數必須在1-365之間"
                )
                return self.error_handler.format_error_response(error)
            
            cleaned_count = await self.link_service.cleanup_old_reports(keep_days)
            
            return self._success_response({
                "cleaned_files": cleaned_count,
                "keep_days": keep_days,
                "cleanup_time": datetime.now().isoformat()
            })
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e, {"operation": "cleanup_reports", "keep_days": keep_days}
            )
            return self.error_handler.format_error_response(error)
    
    def __post_init__(self):
        """後初始化設置"""
        # 設置快取裝飾器的快取實例
        self.check_links = cached_api_call(
            self.cache, CachePolicy.SHORT_TERM
        )(self.check_links.__func__)
    
    def _success_response(self, data: Any) -> Dict[str, Any]:
        """建立成功響應"""
        return {
            "success": True,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
    
    def _validate_check_params(self,
                             target_paths: Optional[List[str]],
                             check_external: bool,
                             check_anchors: bool,
                             output_format: str) -> Optional[Dict[str, Any]]:
        """驗證檢查參數"""
        # 驗證目標路徑
        if target_paths:
            for path in target_paths:
                if not Path(path).exists():
                    error = self.error_handler.create_error(
                        "LINK_CHECK_001",
                        {"path": path},
                        f"路徑不存在: {path}"
                    )
                    return self.error_handler.format_error_response(error)
        
        # 驗證輸出格式
        valid_formats = ["json", "summary"]
        if output_format not in valid_formats:
            error = self.error_handler.create_error(
                "LINK_CHECK_004",
                {"format": output_format, "valid_formats": valid_formats},
                f"不支援的輸出格式: {output_format}"
            )
            return self.error_handler.format_error_response(error)
        
        return None
    
    def _format_summary_response(self, result: CheckResult) -> Dict[str, Any]:
        """格式化摘要響應"""
        return {
            "check_id": result.check_id,
            "timestamp": result.timestamp.isoformat(),
            "summary": {
                "documents_checked": result.documents_checked,
                "total_links": result.total_links_found,
                "valid_links": result.valid_links,
                "broken_links": result.broken_links,
                "success_rate": result.overall_success_rate,
                "has_failures": result.has_failures,
                "duration_ms": result.check_duration_ms
            },
            "recommendations": result.summary.get("recommendations", [])
        }
    
    def _format_detailed_response(self, result: CheckResult) -> Dict[str, Any]:
        """格式化詳細響應"""
        response = self._format_summary_response(result)
        
        # 添加詳細報告資訊
        if result.reports:
            report = result.reports[0]
            response["details"] = {
                "broken_links": [
                    {
                        "text": link.text,
                        "url": link.url,
                        "line_number": link.line_number,
                        "link_type": link.link_type.value,
                        "error_message": link.error_message
                    }
                    for link in report.broken_links
                ],
                "warnings": report.warnings,
                "errors": report.errors,
                "link_distribution": {
                    "internal_links": report.internal_links,
                    "external_links": report.external_links,
                    "anchor_links": report.anchor_links,
                    "file_links": report.file_links
                }
            }
        
        response["configuration"] = result.configuration
        return response


# 全域API實例（為了整合方便）
_api_instance: Optional[LinkCheckAPI] = None

def get_link_check_api(base_path: str) -> LinkCheckAPI:
    """獲取API實例"""
    global _api_instance
    
    if _api_instance is None:
        _api_instance = LinkCheckAPI(base_path)
        # 設置後初始化
        _api_instance.__post_init__()
    
    return _api_instance