"""
連結檢查服務資料模型
Task ID: T3 - 文檔連結有效性修復

定義連結檢查系統的資料結構和模型
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pathlib import Path


class LinkType(Enum):
    """連結類型枚舉"""
    INTERNAL = "internal"  # 內部連結（相對路徑）
    EXTERNAL = "external"  # 外部連結（http/https）
    ANCHOR = "anchor"      # 錨點連結（#開頭）
    FILE = "file"          # 檔案連結


class LinkStatus(Enum):
    """連結狀態枚舉"""
    VALID = "valid"
    INVALID = "invalid" 
    UNREACHABLE = "unreachable"
    BROKEN = "broken"
    UNKNOWN = "unknown"


@dataclass
class Link:
    """連結資料模型"""
    text: str                    # 連結顯示文字
    url: str                     # 連結目標URL
    line_number: int             # 所在行數
    column_start: int            # 起始列位置
    column_end: int              # 結束列位置
    link_type: LinkType          # 連結類型
    status: LinkStatus = LinkStatus.UNKNOWN
    resolved_path: Optional[str] = None  # 解析後的絕對路徑
    error_message: Optional[str] = None  # 錯誤訊息
    
    def __post_init__(self):
        """後處理：自動判斷連結類型"""
        if not self.link_type:
            self.link_type = self._determine_link_type()
    
    def _determine_link_type(self) -> LinkType:
        """判斷連結類型"""
        if self.url.startswith('http://') or self.url.startswith('https://'):
            return LinkType.EXTERNAL
        elif self.url.startswith('#'):
            return LinkType.ANCHOR
        elif '.' in self.url and not self.url.startswith('/'):
            return LinkType.FILE
        else:
            return LinkType.INTERNAL


@dataclass
class Document:
    """文檔資料模型"""
    file_path: str
    relative_path: str
    content: str
    links: List[Link]
    size_bytes: int
    last_modified: datetime
    encoding: str = "utf-8"
    
    def __post_init__(self):
        if not self.links:
            self.links = []


@dataclass 
class ValidationReport:
    """驗證報告資料模型"""
    document_path: str
    scan_timestamp: datetime
    total_links: int
    valid_links: int
    invalid_links: int
    external_links: int
    internal_links: int
    anchor_links: int
    file_links: int
    broken_links: List[Link]
    warnings: List[str]
    errors: List[str]
    scan_duration_ms: float
    
    def __post_init__(self):
        if not self.broken_links:
            self.broken_links = []
        if not self.warnings:
            self.warnings = []
        if not self.errors:
            self.errors = []
    
    @property
    def success_rate(self) -> float:
        """計算成功率"""
        if self.total_links == 0:
            return 100.0
        return (self.valid_links / self.total_links) * 100.0
    
    @property
    def has_issues(self) -> bool:
        """是否有問題"""
        return self.invalid_links > 0 or len(self.errors) > 0


@dataclass
class CheckResult:
    """檢查結果資料模型"""
    check_id: str
    timestamp: datetime
    documents_checked: int
    total_links_found: int
    valid_links: int
    broken_links: int
    check_duration_ms: float
    reports: List[ValidationReport]
    summary: Dict[str, Any]
    configuration: Dict[str, Any]
    
    def __post_init__(self):
        if not self.reports:
            self.reports = []
        if not self.summary:
            self.summary = {}
        if not self.configuration:
            self.configuration = {}
    
    @property
    def overall_success_rate(self) -> float:
        """總體成功率"""
        if self.total_links_found == 0:
            return 100.0
        return (self.valid_links / self.total_links_found) * 100.0
    
    @property 
    def has_failures(self) -> bool:
        """是否有失敗"""
        return self.broken_links > 0


@dataclass
class LinkCheckConfig:
    """連結檢查配置"""
    check_external_links: bool = False  # 是否檢查外部連結
    check_anchors: bool = True          # 是否檢查錨點
    follow_redirects: bool = True       # 是否跟隨重定向
    timeout_seconds: int = 10           # 檢查超時時間
    max_concurrent_checks: int = 5      # 最大並發檢查數
    ignore_patterns: List[str] = None   # 忽略的模式
    base_path: Optional[str] = None     # 基礎路徑
    file_extensions: List[str] = None   # 支援的檔案副檔名
    
    def __post_init__(self):
        if self.ignore_patterns is None:
            self.ignore_patterns = []
        if self.file_extensions is None:
            self.file_extensions = ['.md', '.markdown', '.txt', '.rst']


@dataclass 
class PeriodicCheckSchedule:
    """定期檢查排程"""
    schedule_id: str
    name: str
    interval_hours: int             # 檢查間隔（小時）
    next_check_time: datetime       # 下次檢查時間
    target_directories: List[str]   # 目標目錄
    config: LinkCheckConfig         # 檢查配置
    enabled: bool = True
    last_check_time: Optional[datetime] = None
    last_result_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.target_directories:
            self.target_directories = []


@dataclass
class LinkCheckHistory:
    """連結檢查歷史記錄"""
    history_id: str
    check_result: CheckResult
    archived_at: datetime
    retention_days: int = 30
    
    @property
    def is_expired(self) -> bool:
        """是否已過期"""
        days_since_check = (datetime.now() - self.archived_at).days
        return days_since_check > self.retention_days