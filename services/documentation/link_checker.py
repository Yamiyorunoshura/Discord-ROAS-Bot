"""
連結檢查核心引擎
Task ID: T3 - 文檔連結有效性修復

提供文檔連結解析、驗證和報告功能的核心引擎
"""

import re
import os
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple, AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
import hashlib

from .link_checker_models import (
    Link, Document, ValidationReport, CheckResult, LinkType, LinkStatus,
    LinkCheckConfig
)

logger = logging.getLogger('services.documentation.link_checker')


class LinkChecker:
    """
    連結檢查核心引擎
    
    提供文檔連結的解析、驗證和報告功能，支援：
    - Markdown文件的連結解析
    - 內部連結有效性驗證
    - 錨點連結檢查
    - 批量文檔處理
    - 多種輸出格式
    """
    
    def __init__(self, config: Optional[LinkCheckConfig] = None):
        """
        初始化連結檢查引擎
        
        參數:
            config: 檢查配置，預設為None使用預設配置
        """
        self.config = config or LinkCheckConfig()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_checks)
        
        # 連結解析正規表達式
        self.markdown_link_pattern = re.compile(
            r'\[([^\]]*)\]\(([^)]+)\)',
            re.MULTILINE | re.IGNORECASE
        )
        
        # 錨點提取正規表達式
        self.header_pattern = re.compile(
            r'^#+\s+(.+?)(?:\s*\{[^}]*\})?\s*$',
            re.MULTILINE
        )
        
        # 快取已檢查的檔案和錨點
        self._file_cache: Dict[str, bool] = {}
        self._anchor_cache: Dict[str, Set[str]] = {}
        self._cache_timestamp = time.time()
        self._cache_ttl = 300  # 5分鐘快取
        
    def scan_directory(self, path: str) -> List[Document]:
        """
        掃描指定目錄中的Markdown文檔
        
        參數:
            path: 目錄路徑
            
        返回:
            文檔物件列表
        """
        documents = []
        scan_path = Path(path)
        
        if not scan_path.exists():
            logger.warning(f"掃描路徑不存在: {path}")
            return documents
        
        logger.info(f"開始掃描目錄: {path}")
        
        for file_path in scan_path.rglob("*"):
            if (file_path.is_file() and 
                file_path.suffix.lower() in self.config.file_extensions):
                
                # 檢查是否應該忽略此檔案
                if self._should_ignore_file(str(file_path)):
                    continue
                
                try:
                    document = self._load_document(file_path)
                    if document:
                        documents.append(document)
                        logger.debug(f"載入文檔: {file_path}")
                except Exception as e:
                    logger.error(f"載入文檔失敗 {file_path}: {e}")
        
        logger.info(f"掃描完成，找到 {len(documents)} 個文檔")
        return documents
    
    def _should_ignore_file(self, file_path: str) -> bool:
        """檢查檔案是否應該被忽略"""
        for pattern in self.config.ignore_patterns:
            if re.search(pattern, file_path):
                return True
        return False
    
    def _load_document(self, file_path: Path) -> Optional[Document]:
        """載入單個文檔"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析文檔中的連結
            links = self._extract_links(content, str(file_path))
            
            # 計算相對路徑
            if self.config.base_path:
                base = Path(self.config.base_path)
                try:
                    relative_path = str(file_path.relative_to(base))
                except ValueError:
                    relative_path = str(file_path)
            else:
                relative_path = str(file_path)
            
            return Document(
                file_path=str(file_path),
                relative_path=relative_path,
                content=content,
                links=links,
                size_bytes=file_path.stat().st_size,
                last_modified=datetime.fromtimestamp(file_path.stat().st_mtime)
            )
            
        except Exception as e:
            logger.error(f"載入文檔失敗 {file_path}: {e}")
            return None
    
    def _extract_links(self, content: str, source_file: str) -> List[Link]:
        """從文檔內容中提取連結"""
        links = []
        lines = content.split('\n')
        
        for line_idx, line in enumerate(lines, 1):
            for match in self.markdown_link_pattern.finditer(line):
                text = match.group(1)
                url = match.group(2).strip()
                
                # 跳過空連結
                if not url:
                    continue
                
                link = Link(
                    text=text,
                    url=url,
                    line_number=line_idx,
                    column_start=match.start(),
                    column_end=match.end(),
                    link_type=self._determine_link_type(url)
                )
                
                links.append(link)
        
        logger.debug(f"從 {source_file} 提取了 {len(links)} 個連結")
        return links
    
    def _determine_link_type(self, url: str) -> LinkType:
        """判斷連結類型"""
        if url.startswith(('http://', 'https://')):
            return LinkType.EXTERNAL
        elif url.startswith('#'):
            return LinkType.ANCHOR
        elif url.startswith('/') or url.startswith('./') or url.startswith('../'):
            return LinkType.INTERNAL
        elif '.' in url and not '/' in url:
            return LinkType.FILE
        else:
            return LinkType.INTERNAL
    
    async def validate_links(self, documents: List[Document]) -> ValidationReport:
        """
        驗證文檔中的連結有效性
        
        參數:
            documents: 要驗證的文檔列表
            
        返回:
            驗證報告
        """
        start_time = time.time()
        total_links = 0
        valid_links = 0
        invalid_links = 0
        broken_links = []
        warnings = []
        errors = []
        
        # 統計不同類型的連結
        external_links = 0
        internal_links = 0 
        anchor_links = 0
        file_links = 0
        
        logger.info(f"開始驗證 {len(documents)} 個文檔中的連結")
        
        # 建立所有文檔的錨點索引
        anchor_index = await self._build_anchor_index(documents)
        
        for document in documents:
            for link in document.links:
                total_links += 1
                
                # 統計連結類型
                if link.link_type == LinkType.EXTERNAL:
                    external_links += 1
                elif link.link_type == LinkType.INTERNAL:
                    internal_links += 1
                elif link.link_type == LinkType.ANCHOR:
                    anchor_links += 1
                elif link.link_type == LinkType.FILE:
                    file_links += 1
                
                # 驗證連結
                is_valid = await self._validate_single_link(
                    link, document.file_path, anchor_index
                )
                
                if is_valid:
                    valid_links += 1
                    link.status = LinkStatus.VALID
                else:
                    invalid_links += 1
                    link.status = LinkStatus.INVALID
                    broken_links.append(link)
        
        # 檢查孤立錨點（定義了但未使用的錨點）
        orphaned_anchors = self._find_orphaned_anchors(documents, anchor_index)
        if orphaned_anchors:
            warnings.extend([
                f"發現未使用的錨點: {anchor}" 
                for anchor in orphaned_anchors[:5]  # 限制警告數量
            ])
        
        scan_duration = (time.time() - start_time) * 1000
        
        # 建立總合報告（針對單個或多個文檔的彙總）
        document_path = documents[0].file_path if len(documents) == 1 else "多個文檔"
        
        report = ValidationReport(
            document_path=document_path,
            scan_timestamp=datetime.now(),
            total_links=total_links,
            valid_links=valid_links,
            invalid_links=invalid_links,
            external_links=external_links,
            internal_links=internal_links,
            anchor_links=anchor_links,
            file_links=file_links,
            broken_links=broken_links,
            warnings=warnings,
            errors=errors,
            scan_duration_ms=scan_duration
        )
        
        logger.info(f"連結驗證完成: {valid_links}/{total_links} 有效 ({report.success_rate:.1f}%)")
        return report
    
    async def _build_anchor_index(self, documents: List[Document]) -> Dict[str, Set[str]]:
        """建立文檔錨點索引"""
        anchor_index = {}
        
        for document in documents:
            anchors = self._extract_anchors(document.content)
            if anchors:
                anchor_index[document.file_path] = anchors
                # 同時加入相對路徑索引
                anchor_index[document.relative_path] = anchors
        
        return anchor_index
    
    def _extract_anchors(self, content: str) -> Set[str]:
        """從文檔內容中提取錨點"""
        anchors = set()
        
        # 提取標題作為錨點
        for match in self.header_pattern.finditer(content):
            title = match.group(1).strip()
            # 轉換為GitHub風格的錨點
            anchor = self._title_to_anchor(title)
            anchors.add(anchor)
        
        # 提取顯式錨點 (如 {#custom-anchor})
        explicit_anchors = re.findall(r'\{#([^}]+)\}', content)
        anchors.update(explicit_anchors)
        
        return anchors
    
    def _title_to_anchor(self, title: str) -> str:
        """將標題轉換為錨點格式"""
        # 移除特殊字符，保留字母數字和空格
        clean_title = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', title)
        # 轉小寫並將空格替換為連字符
        anchor = clean_title.lower().replace(' ', '-').replace('--', '-')
        # 移除前後的連字符
        return anchor.strip('-')
    
    async def _validate_single_link(
        self, 
        link: Link, 
        source_file: str, 
        anchor_index: Dict[str, Set[str]]
    ) -> bool:
        """驗證單個連結"""
        try:
            if link.link_type == LinkType.EXTERNAL:
                # 外部連結檢查（如果配置允許）
                if self.config.check_external_links:
                    return await self._check_external_link(link.url)
                else:
                    # 預設外部連結為有效
                    return True
            
            elif link.link_type == LinkType.ANCHOR:
                # 錨點連結檢查
                return self._check_anchor_link(link.url, source_file, anchor_index)
            
            elif link.link_type in [LinkType.INTERNAL, LinkType.FILE]:
                # 內部檔案連結檢查
                return await self._check_internal_link(link.url, source_file)
            
            return True
            
        except Exception as e:
            logger.error(f"驗證連結失敗 {link.url}: {e}")
            link.error_message = str(e)
            return False
    
    def _check_anchor_link(
        self, 
        anchor_url: str, 
        source_file: str, 
        anchor_index: Dict[str, Set[str]]
    ) -> bool:
        """檢查錨點連結"""
        if not self.config.check_anchors:
            return True
        
        # 移除開頭的 #
        anchor = anchor_url.lstrip('#')
        
        # 檢查當前文檔是否有此錨點
        current_anchors = anchor_index.get(source_file, set())
        return anchor in current_anchors
    
    async def _check_internal_link(self, link_url: str, source_file: str) -> bool:
        """檢查內部連結"""
        try:
            source_path = Path(source_file).parent
            
            # 處理相對路徑
            if link_url.startswith('./'):
                target_path = source_path / link_url[2:]
            elif link_url.startswith('../'):
                target_path = source_path / link_url
            elif link_url.startswith('/'):
                # 絕對路徑（相對於項目根目錄）
                if self.config.base_path:
                    target_path = Path(self.config.base_path) / link_url.lstrip('/')
                else:
                    target_path = Path(link_url)
            else:
                # 相對路徑
                target_path = source_path / link_url
            
            # 解析並規範化路徑
            resolved_path = target_path.resolve()
            
            # 檢查檔案是否存在（使用快取）
            path_str = str(resolved_path)
            if path_str in self._file_cache:
                return self._file_cache[path_str]
            
            exists = resolved_path.exists()
            self._file_cache[path_str] = exists
            
            return exists
            
        except Exception as e:
            logger.debug(f"檢查內部連結失敗 {link_url}: {e}")
            return False
    
    async def _check_external_link(self, url: str) -> bool:
        """檢查外部連結（預留功能）"""
        # 這裡可以實作HTTP請求檢查
        # 但根據T3需求，主要關注內部連結
        logger.debug(f"跳過外部連結檢查: {url}")
        return True
    
    def _find_orphaned_anchors(
        self, 
        documents: List[Document], 
        anchor_index: Dict[str, Set[str]]
    ) -> List[str]:
        """尋找孤立的錨點（定義了但未使用）"""
        defined_anchors = set()
        used_anchors = set()
        
        # 收集所有已定義的錨點
        for anchors in anchor_index.values():
            defined_anchors.update(anchors)
        
        # 收集所有使用的錨點
        for document in documents:
            for link in document.links:
                if link.link_type == LinkType.ANCHOR:
                    anchor = link.url.lstrip('#')
                    used_anchors.add(anchor)
        
        # 找出未使用的錨點
        orphaned = defined_anchors - used_anchors
        return list(orphaned)
    
    def generate_report(self, report: ValidationReport, format: str = "markdown") -> str:
        """
        生成檢查報告
        
        參數:
            report: 驗證報告
            format: 輸出格式 ("markdown", "json", "csv", "text")
            
        返回:
            格式化的報告內容
        """
        if format.lower() == "json":
            return self._generate_json_report(report)
        elif format.lower() == "csv":
            return self._generate_csv_report(report)
        elif format.lower() == "text":
            return self._generate_text_report(report)
        else:
            return self._generate_markdown_report(report)
    
    def _generate_markdown_report(self, report: ValidationReport) -> str:
        """生成Markdown格式報告"""
        lines = [
            "# 文檔連結檢查報告",
            "",
            f"**檢查時間：** {report.scan_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**檢查文檔：** {report.document_path}",
            f"**掃描耗時：** {report.scan_duration_ms:.0f}ms",
            "",
            "## 統計摘要",
            "",
            f"- **總連結數：** {report.total_links}",
            f"- **有效連結：** {report.valid_links}",
            f"- **無效連結：** {report.invalid_links}",
            f"- **成功率：** {report.success_rate:.1f}%",
            "",
            "### 連結類型分布",
            "",
            f"- 內部連結：{report.internal_links}",
            f"- 外部連結：{report.external_links}",
            f"- 錨點連結：{report.anchor_links}",
            f"- 檔案連結：{report.file_links}",
            ""
        ]
        
        if report.broken_links:
            lines.extend([
                "## 無效連結詳細信息",
                "",
                "| 連結文字 | 目標URL | 位置 | 錯誤信息 |",
                "|---------|--------|------|----------|"
            ])
            
            for link in report.broken_links:
                error_msg = link.error_message or "連結無效"
                lines.append(
                    f"| {link.text} | {link.url} | "
                    f"第{link.line_number}行 | {error_msg} |"
                )
            lines.append("")
        
        if report.warnings:
            lines.extend([
                "## 警告信息",
                ""
            ])
            for warning in report.warnings:
                lines.append(f"⚠️ {warning}")
            lines.append("")
        
        if report.errors:
            lines.extend([
                "## 錯誤信息", 
                ""
            ])
            for error in report.errors:
                lines.append(f"❌ {error}")
            lines.append("")
        
        # 添加建議
        if report.has_issues:
            lines.extend([
                "## 修復建議",
                "",
                "1. 檢查並修復上述列出的無效連結",
                "2. 確保相對路徑指向正確的檔案位置", 
                "3. 驗證錨點連結對應的標題是否存在",
                "4. 考慮使用絕對路徑以避免路徑解析問題",
                ""
            ])
        
        return "\n".join(lines)
    
    def _generate_json_report(self, report: ValidationReport) -> str:
        """生成JSON格式報告"""
        import json
        
        # 將報告轉換為可序列化的字典
        report_dict = {
            "document_path": report.document_path,
            "scan_timestamp": report.scan_timestamp.isoformat(),
            "total_links": report.total_links,
            "valid_links": report.valid_links,
            "invalid_links": report.invalid_links,
            "success_rate": round(report.success_rate, 2),
            "external_links": report.external_links,
            "internal_links": report.internal_links,
            "anchor_links": report.anchor_links,
            "file_links": report.file_links,
            "scan_duration_ms": round(report.scan_duration_ms, 2),
            "has_issues": report.has_issues,
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
            "errors": report.errors
        }
        
        return json.dumps(report_dict, indent=2, ensure_ascii=False)
    
    def _generate_csv_report(self, report: ValidationReport) -> str:
        """生成CSV格式報告"""
        lines = [
            "連結文字,目標URL,行數,連結類型,狀態,錯誤信息"
        ]
        
        for link in report.broken_links:
            lines.append(
                f'"{link.text}","{link.url}",{link.line_number},'
                f'"{link.link_type.value}","無效","{link.error_message or ""}"'
            )
        
        return "\n".join(lines)
    
    def _generate_text_report(self, report: ValidationReport) -> str:
        """生成純文字格式報告"""
        lines = [
            "文檔連結檢查報告",
            "=" * 50,
            f"檢查時間: {report.scan_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"檢查文檔: {report.document_path}",
            f"掃描耗時: {report.scan_duration_ms:.0f}ms",
            "",
            "統計摘要:",
            f"  總連結數: {report.total_links}",
            f"  有效連結: {report.valid_links}",
            f"  無效連結: {report.invalid_links}",
            f"  成功率: {report.success_rate:.1f}%",
            ""
        ]
        
        if report.broken_links:
            lines.extend([
                "無效連結:",
                "-" * 30
            ])
            for i, link in enumerate(report.broken_links, 1):
                lines.append(
                    f"{i}. [{link.text}]({link.url}) "
                    f"- 第{link.line_number}行"
                )
                if link.error_message:
                    lines.append(f"   錯誤: {link.error_message}")
            lines.append("")
        
        return "\n".join(lines)
    
    def clear_cache(self):
        """清理快取"""
        self._file_cache.clear()
        self._anchor_cache.clear()
        self._cache_timestamp = time.time()
        logger.debug("連結檢查器快取已清理")
    
    def get_cache_stats(self) -> dict:
        """獲取快取統計"""
        return {
            "file_cache_size": len(self._file_cache),
            "anchor_cache_size": len(self._anchor_cache),
            "cache_age_seconds": time.time() - self._cache_timestamp,
            "cache_ttl_seconds": self._cache_ttl
        }
    
    async def close(self):
        """關閉資源"""
        self.executor.shutdown(wait=True)
        logger.debug("連結檢查器已關閉")