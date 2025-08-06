"""
反可執行檔案保護模組配置文件
包含所有預設值、常數定義和工具函數
"""

import re
import urllib.parse as urlparse

# ────────────────────────────
# 常數定義
# ────────────────────────────
MIN_FILE_EXTENSION_PARTS = 3
CONTENT_PREVIEW_MAX_LENGTH = 500
MAX_FILE_SIZE = 100  # MB

# ────────────────────────────
# 預設配置值
# ────────────────────────────
DEFAULTS = {
    "enabled": "false",
    "delete_message": "🚫 偵測到可執行檔案,已自動刪除",
    "notify_channel": "",
    "whitelist_admins": "true",
    "check_attachments": "true",
    "check_links": "true",
    "strict_mode": "false",  # 嚴格模式:檢查更多檔案類型
}

# ────────────────────────────
# 常數定義
# ────────────────────────────
# 危險檔案副檔名
DANGEROUS_EXTENSIONS = {
    # Windows 可執行檔案
    "exe",
    "com",
    "scr",
    "bat",
    "cmd",
    "pif",
    "vbs",
    "vbe",
    "js",
    "jse",
    "wsf",
    "wsh",
    "msc",
    "msi",
    "msp",
    "hta",
    "cpl",
    "scf",
    "lnk",
    "inf",
    "reg",
    "ps1",
    "ps1xml",
    "ps2",
    "ps2xml",
    "psc1",
    "psc2",
    "msh",
    "msh1",
    "msh2",
    "mshxml",
    "msh1xml",
    "msh2xml",
    # 其他平台可執行檔案
    "app",
    "deb",
    "pkg",
    "rpm",
    "dmg",
    "run",
    "bin",
    "command",
    "workflow",
    "action",
    "sh",
    "bash",
    "zsh",
    "fish",
    "csh",
    "tcsh",
    # 危險腳本
    "py",
    "rb",
    "pl",
    "php",
    "asp",
    "aspx",
    "jsp",
    "jar",
    "zip",
    "rar",
    "7z",
    "tar",
    "gz",
    "bz2",
    "xz",
    "cab",
    "ace",
    # 其他危險檔案
    "iso",
    "img",
    "vhd",
    "vmdk",
    "ova",
    "ovf",
}

# 嚴格模式額外檢查的副檔名
STRICT_EXTENSIONS = {
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "docm",
    "xlsm",
    "pptm",
    "dot",
    "dotx",
    "dotm",
    "xlt",
    "xltx",
    "xltm",
    "pot",
    "potx",
    "potm",
    # PDF 文件(可能包含惡意 JavaScript)
    "pdf",
    # 其他腳本和配置檔案
    "cfg",
    "conf",
    "ini",
    "xml",
    "json",
    "yaml",
    "yml",
    # 資料庫檔案
    "db",
    "sqlite",
    "mdb",
    "accdb",
    # 其他壓縮格式
    "tar.gz",
    "tar.bz2",
    "tar.xz",
    "tgz",
    "tbz2",
    "txz",
}

SAFE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "webp",
    "svg",
    "ico",
    "tiff",
    "tif",
    # 音訊檔案
    "mp3",
    "wav",
    "flac",
    "aac",
    "ogg",
    "wma",
    "m4a",
    "opus",
    # 視頻檔案
    "mp4",
    "avi",
    "mkv",
    "mov",
    "wmv",
    "flv",
    "webm",
    "m4v",
    "3gp",
    # 文字檔案
    "txt",
    "md",
    "rtf",
    "log",
    "csv",
    "tsv",
    # 字體檔案
    "ttf",
    "otf",
    "woff",
    "woff2",
    "eot",
}

# 危險 MIME 類型
DANGEROUS_MIME_TYPES = {
    "application/x-executable",
    "application/x-msdos-program",
    "application/x-msdownload",
    "application/x-winexe",
    "application/x-dosexec",
    "application/octet-stream",  # 通用二進位檔案
    "application/x-sharedlib",
    "application/x-shellscript",
    "text/x-shellscript",
    "application/x-perl",
    "application/x-python-code",
    "application/x-ruby",
    "application/x-php",
    "application/javascript",
    "text/javascript",
    "application/x-javascript",
    "application/vnd.microsoft.portable-executable",
}

# 魔法字節簽名用於檢測文件類型
MAGIC_SIGNATURES = {
    # Windows 可執行檔案
    b"MZ": "exe",  # DOS/Windows 可執行檔案
    b"PK": "zip",  # ZIP 壓縮檔案
    b"\x7fELF": "elf",  # Linux ELF 可執行檔案
    b"\xca\xfe\xba\xbe": "java_class",  # Java class 檔案
    b"\xfe\xed\xfa\xce": "macho",  # macOS Mach-O 可執行檔案
    b"\xfe\xed\xfa\xcf": "macho_64",  # macOS Mach-O 64位可執行檔案
    b"\xcf\xfa\xed\xfe": "macho_reverse",  # macOS Mach-O 反向字節序
    b"\xce\xfa\xed\xfe": "macho_64_reverse",  # macOS Mach-O 64位反向字節序
    b"Rar!": "rar",  # RAR 壓縮檔案
    b"7z\xbc\xaf'\x1c": "7z",  # 7-Zip 壓縮檔案
    b"\x00\x00\x01\x00": "ico",  # Windows 圖標檔案
    b"<!DOCTYPE html": "html",  # HTML 檔案
    b"<?xml": "xml",  # XML 檔案
    b"#!/bin/sh": "shell_script",  # Shell 腳本
    b"#!/bin/bash": "bash_script",  # Bash 腳本
    b"#!/usr/bin/python": "python_script",  # Python 腳本
    b"#!/usr/bin/perl": "perl_script",  # Perl 腳本
}

# 錯誤代碼映射
ERROR_CODES = {
    "CONFIG_ERROR": "ANTI_EXECUTABLE_CONFIG_ERROR",
    "DATABASE_ERROR": "ANTI_EXECUTABLE_DATABASE_ERROR",
    "FILE_CHECK_ERROR": "ANTI_EXECUTABLE_FILE_CHECK_ERROR",
    "PERMISSION_ERROR": "ANTI_EXECUTABLE_PERMISSION_ERROR",
    "MESSAGE_HANDLER_ERROR": "ANTI_EXECUTABLE_MESSAGE_HANDLER_ERROR",
    "MALICIOUS_FILE_HANDLER_ERROR": "ANTI_EXECUTABLE_MALICIOUS_FILE_HANDLER_ERROR",
    "PANEL_ERROR": "ANTI_EXECUTABLE_PANEL_ERROR",
}


# ────────────────────────────
# 工具函數
# ────────────────────────────
def get_file_extension(filename: str) -> str:
    """
    獲取檔案副檔名

    Args:
        filename: 檔案名稱

    Returns:
        str: 副檔名(小寫,不包含點)
    """
    try:
        if "." not in filename:
            return ""

        parts = filename.lower().split(".")
        if (
            len(parts) >= MIN_FILE_EXTENSION_PARTS
            and f"{parts[-2]}.{parts[-1]}" in STRICT_EXTENSIONS
        ):
            return f"{parts[-2]}.{parts[-1]}"

        return parts[-1]
    except Exception:
        return ""


def is_dangerous_file(filename: str, strict_mode: bool = False) -> bool:
    """
    檢查檔案是否為危險檔案

    Args:
        filename: 檔案名稱
        strict_mode: 是否使用嚴格模式

    Returns:
        bool: 是否為危險檔案
    """
    try:
        ext = get_file_extension(filename)
        if not ext:
            return False

        # 檢查基本危險副檔名
        if ext in DANGEROUS_EXTENSIONS:
            return True

        # 嚴格模式額外檢查
        return bool(strict_mode and ext in STRICT_EXTENSIONS)
    except Exception:
        return False


def is_safe_file(filename: str) -> bool:
    """
    檢查檔案是否為安全檔案

    Args:
        filename: 檔案名稱

    Returns:
        bool: 是否為安全檔案
    """
    try:
        ext = get_file_extension(filename)
        return ext in SAFE_EXTENSIONS
    except Exception:
        return False


def is_dangerous_mime_type(mime_type: str) -> bool:
    """
    檢查 MIME 類型是否為危險類型

    Args:
        mime_type: MIME 類型

    Returns:
        bool: 是否為危險 MIME 類型
    """
    try:
        return mime_type.lower() in DANGEROUS_MIME_TYPES
    except Exception:
        return False


def extract_urls_from_text(text: str) -> list[str]:
    """
    從文字中提取 URL

    Args:
        text: 要檢查的文字

    Returns:
        List[str]: 找到的 URL 列表
    """
    try:
        # 簡單的 URL 檢測正則表達式
        url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)
        return url_pattern.findall(text)
    except Exception:
        return []


def is_executable_url(url: str) -> bool:
    """
    檢查 URL 是否指向可執行檔案

    Args:
        url: 要檢查的 URL

    Returns:
        bool: 是否指向可執行檔案
    """
    try:
        # 從 URL 中提取檔案名稱
        parsed = urlparse.urlparse(url)
        path = parsed.path

        filename = path.split("/")[-1] if "/" in path else path

        # 移除查詢參數
        if "?" in filename:
            filename = filename.split("?")[0]

        return is_dangerous_file(filename)
    except Exception:
        return False


def format_file_list(files: list[str], max_length: int = 1000) -> str:
    """
    格式化檔案列表為字串

    Args:
        files: 檔案列表
        max_length: 最大字串長度

    Returns:
        str: 格式化後的字串
    """
    try:
        if not files:
            return "(無)"

        result = []
        current_length = 0

        for file in files:
            line = f"• {file}"
            if current_length + len(line) + 1 > max_length:
                remaining = len(files) - len(result)
                if remaining > 0:
                    result.append(f"... 還有 {remaining} 個檔案")
                break

            result.append(line)
            current_length += len(line) + 1

        return "\n".join(result)
    except Exception:
        return "(解析錯誤)"


def get_file_risk_level(filename: str, strict_mode: bool = False) -> str:
    """
    獲取檔案風險等級

    Args:
        filename: 檔案名稱
        strict_mode: 是否使用嚴格模式

    Returns:
        str: 風險等級(高、中、低、安全)
    """
    try:
        ext = get_file_extension(filename)
        if not ext:
            return "未知"

        # 按優先級檢查風險等級
        high_risk = {"exe", "com", "scr", "bat", "cmd", "vbs", "js", "msi", "ps1"}

        if ext in SAFE_EXTENSIONS:
            risk_level = "安全"
        elif ext in high_risk:
            risk_level = "高"
        elif ext in DANGEROUS_EXTENSIONS:
            risk_level = "中"
        elif strict_mode and ext in STRICT_EXTENSIONS:
            risk_level = "低"
        else:
            risk_level = "未知"

        return risk_level
    except Exception:
        return "未知"


def get_config_description(key: str) -> str:
    """
    獲取配置項目的描述

    Args:
        key: 配置鍵名

    Returns:
        str: 配置描述
    """
    descriptions = {
        "enabled": "是否啟用反可執行檔案保護",
        "delete_message": "刪除危險檔案時顯示的訊息",
        "notify_channel": "管理員通知頻道 ID",
        "whitelist_admins": "是否將管理員加入白名單",
        "check_attachments": "是否檢查附件",
        "check_links": "是否檢查連結中的檔案",
        "strict_mode": "是否啟用嚴格模式(檢查更多檔案類型)",
    }

    return descriptions.get(key, "未知配置項目")


def get_stats_description(key: str) -> str:
    """
    獲取統計項目的描述

    Args:
        key: 統計鍵名

    Returns:
        str: 統計描述
    """
    descriptions = {
        "files_blocked": "已阻止的危險檔案數量",
        "messages_deleted": "已刪除的訊息數量",
        "attachments_checked": "已檢查的附件數量",
        "links_checked": "已檢查的連結數量",
        "high_risk_files": "高風險檔案數量",
        "medium_risk_files": "中風險檔案數量",
        "low_risk_files": "低風險檔案數量",
        "false_positives": "誤報次數",
    }

    return descriptions.get(key, "未知統計項目")
