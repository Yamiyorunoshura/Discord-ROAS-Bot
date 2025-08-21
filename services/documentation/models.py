"""
文檔服務資料模型
Task ID: 11 - 建立文件和部署準備

定義文檔系統相關的資料模型
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class DocumentCategory(Enum):
    """文檔類別枚舉"""
    API = "api"
    USER = "user"
    ADMIN = "admin"
    TECHNICAL = "technical"
    ARCHITECTURE = "architecture"
    DEVELOPER = "developer"
    FAQ = "faq"
    TROUBLESHOOTING = "troubleshooting"


class DocumentFormat(Enum):
    """文檔格式枚舉"""
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class DocumentStatus(Enum):
    """文檔狀態枚舉"""
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    OUTDATED = "outdated"


@dataclass
class DocumentConfig:
    """文檔配置資料模型"""
    id: str
    category: DocumentCategory
    path: str
    title: str
    description: Optional[str] = None
    format: DocumentFormat = DocumentFormat.MARKDOWN
    status: DocumentStatus = DocumentStatus.DRAFT
    template_path: Optional[str] = None
    auto_generate: bool = False
    update_frequency: Optional[int] = None  # 小時
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class DocumentVersion:
    """文檔版本資料模型"""
    id: str
    document_id: str
    version: str
    content_hash: str
    file_path: str
    size_bytes: int
    author: str
    commit_message: Optional[str] = None
    is_current: bool = False
    metadata: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class DocumentGenerationRequest:
    """文檔生成請求資料模型"""
    document_id: str
    force_regenerate: bool = False
    include_examples: bool = True
    include_changelog: bool = True
    target_format: DocumentFormat = DocumentFormat.MARKDOWN
    custom_template: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DocumentValidationResult:
    """文檔驗證結果資料模型"""
    document_id: str
    is_valid: bool
    completeness_score: float  # 0.0 - 1.0
    accuracy_score: float      # 0.0 - 1.0
    readability_score: float   # 0.0 - 5.0
    issues: List[str] = None
    warnings: List[str] = None
    suggestions: List[str] = None
    validation_timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.warnings is None:
            self.warnings = []
        if self.suggestions is None:
            self.suggestions = []
        if self.validation_timestamp is None:
            self.validation_timestamp = datetime.now()


@dataclass
class DocumentationMetrics:
    """文檔系統指標資料模型"""
    total_documents: int
    documents_by_category: Dict[str, int]
    documents_by_status: Dict[str, int]
    total_size_bytes: int
    average_completeness: float
    average_accuracy: float
    average_readability: float
    outdated_documents: int
    last_update_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.last_update_time is None:
            self.last_update_time = datetime.now()


@dataclass
class APIDocumentationInfo:
    """API文檔信息資料模型"""
    service_name: str
    class_name: str
    method_name: str
    description: str
    parameters: List[Dict[str, Any]]
    return_type: str
    return_description: str
    exceptions: List[Dict[str, str]]
    examples: List[Dict[str, str]]
    since_version: Optional[str] = None
    deprecated: bool = False
    deprecation_notice: Optional[str] = None
    
    def __post_init__(self):
        if not self.parameters:
            self.parameters = []
        if not self.exceptions:
            self.exceptions = []
        if not self.examples:
            self.examples = []