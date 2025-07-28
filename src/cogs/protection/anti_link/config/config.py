"""
反惡意連結保護模組配置文件
包含所有預設值、常數定義和工具函數
"""

import re
import urllib.parse as up
from typing import Any

# ────────────────────────────
# 預設配置值
# ────────────────────────────
DEFAULTS = {
    "enabled": "true",
    "whitelist": "",
    "blacklist": "",
    "delete_message": "🚫 偵測到惡意連結,已自動刪除",
    "notify_channel": "",
    "whitelist_admins": "true",
    "check_embeds": "true",
    "auto_update": "true",
}

# ────────────────────────────
# 常數定義
# ────────────────────────────
# URL 檢測正則表達式
URL_PATTERN = re.compile(r"https?://[A-Za-z0-9\.\-_%]+\.[A-Za-z]{2,}[^ <]*", re.I)

# 預設白名單(安全的網域)
DEFAULT_WHITELIST = {
    "discord.com",
    "discord.gg",
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "github.com",
    "gist.github.com",
    "google.com",
    "googleapis.com",
    "twitter.com",
    "t.co",
    "reddit.com",
    "redd.it",
    "imgur.com",
    "i.imgur.com",
    "twitch.tv",
    "clips.twitch.tv",
    "steamcommunity.com",
    "store.steampowered.com",
    "wikipedia.org",
    "wikimedia.org",
    "microsoft.com",
    "office.com",
    "apple.com",
    "icloud.com",
    "dropbox.com",
    "drive.google.com",
    "zoom.us",
    "teams.microsoft.com",
}

# 威脅情資來源配置
THREAT_FEEDS = {
    "URLHaus": {
        "url": "https://urlhaus.abuse.ch/downloads/hostfile/",
        "format": "text",
        "enabled": True,
        "description": "URLHaus 惡意 URL 資料庫",
    },
    "OpenPhish": {
        "url": "https://openphish.com/feed.txt",
        "format": "text",
        "enabled": True,
        "description": "OpenPhish 釣魚網站資料庫",
    },
    "URLHaus-CSV": {
        "url": "https://urlhaus.abuse.ch/downloads/csv_recent/",
        "format": "csv",
        "enabled": False,  # 預設停用,因為資料量較大
        "description": "URLHaus CSV 格式資料",
    },
}

# 錯誤代碼映射
ERROR_CODES = {
    "CONFIG_ERROR": "ANTI_LINK_CONFIG_ERROR",
    "DATABASE_ERROR": "ANTI_LINK_DATABASE_ERROR",
    "NETWORK_ERROR": "ANTI_LINK_NETWORK_ERROR",
    "PARSE_ERROR": "ANTI_LINK_PARSE_ERROR",
    "PERMISSION_ERROR": "ANTI_LINK_PERMISSION_ERROR",
    "MESSAGE_HANDLER_ERROR": "ANTI_LINK_MESSAGE_HANDLER_ERROR",
    "MALICIOUS_LINK_HANDLER_ERROR": "ANTI_LINK_MALICIOUS_LINK_HANDLER_ERROR",
    "BLACKLIST_UPDATE_ERROR": "ANTI_LINK_BLACKLIST_UPDATE_ERROR",
    "MANUAL_UPDATE_ERROR": "ANTI_LINK_MANUAL_UPDATE_ERROR",
    "PANEL_ERROR": "ANTI_LINK_PANEL_ERROR",
}


# ────────────────────────────
# 工具函數
# ────────────────────────────
def extract_domain(url: str) -> str:
    """
    從 URL 中提取網域名稱

    Args:
        url: 要解析的 URL

    Returns:
        str: 網域名稱,如果解析失敗返回空字串
    """
    try:
        # 確保 URL 有協議
        if not url.startswith(("http://", "https://")):
            url = "http://" + url

        parsed = up.urlparse(url)
        domain = parsed.netloc.lower()

        # 移除端口號
        if ":" in domain:
            domain = domain.split(":")[0]

        # 移除 www. 前綴
        if domain.startswith("www."):
            domain = domain[4:]

        return domain
    except Exception:
        return ""


def normalize_domain(domain: str) -> str:
    """
    標準化網域名稱

    Args:
        domain: 原始網域名稱

    Returns:
        str: 標準化後的網域名稱
    """
    try:
        domain = domain.lower().strip()

        # 移除協議
        if domain.startswith(("http://", "https://")):
            domain = up.urlparse(domain).netloc

        # 移除端口號
        if ":" in domain:
            domain = domain.split(":")[0]

        # 移除 www. 前綴
        if domain.startswith("www."):
            domain = domain[4:]

        # 移除路徑
        if "/" in domain:
            domain = domain.split("/")[0]

        return domain
    except Exception:
        return ""


def is_whitelisted(domain: str, whitelist: set[str]) -> bool:
    """
    檢查網域是否在白名單中

    Args:
        domain: 要檢查的網域
        whitelist: 白名單集合

    Returns:
        bool: 是否在白名單中
    """
    try:
        domain = normalize_domain(domain)
        if not domain:
            return False

        # 直接匹配
        if domain in whitelist:
            return True

        # 檢查子網域
        return any(domain.endswith("." + whitelisted) for whitelisted in whitelist)
    except Exception:
        return False


def parse_domain_list(domain_str: str) -> set[str]:
    """
    解析網域列表字串

    Args:
        domain_str: 以逗號分隔的網域列表

    Returns:
        Set[str]: 標準化後的網域集合
    """
    try:
        if not domain_str:
            return set()

        domains = set()
        for domain in domain_str.split(","):
            normalized = normalize_domain(domain.strip())
            if normalized:
                domains.add(normalized)

        return domains
    except Exception:
        return set()


def validate_domain(domain: str) -> bool:
    """
    驗證網域格式是否正確

    Args:
        domain: 要驗證的網域

    Returns:
        bool: 是否為有效網域
    """
    try:
        domain = normalize_domain(domain)
        if not domain:
            return False

        # 基本格式檢查
        if not re.match(
            r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$",
            domain,
        ):
            return False

        # 檢查是否包含有效的 TLD
        if "." not in domain:
            return False

        # 檢查 TLD 長度
        tld = domain.split(".")[-1]
        return not len(tld) < 2
    except Exception:
        return False


def get_domain_info(domain: str) -> dict[str, Any]:
    """
    獲取網域詳細資訊

    Args:
        domain: 網域名稱

    Returns:
        Dict[str, Any]: 網域資訊
    """
    try:
        import tldextract

        extracted = tldextract.extract(domain)
        return {
            "domain": extracted.domain,
            "suffix": extracted.suffix,
            "subdomain": extracted.subdomain,
            "registered_domain": extracted.registered_domain,
            "fqdn": extracted.fqdn,
            "is_valid": bool(extracted.domain and extracted.suffix),
        }
    except Exception:
        return {
            "domain": "",
            "suffix": "",
            "subdomain": "",
            "registered_domain": "",
            "fqdn": domain,
            "is_valid": False,
        }


def format_domain_list(domains: set[str], max_length: int = 1000) -> str:
    """
    格式化網域列表為字串

    Args:
        domains: 網域集合
        max_length: 最大字串長度

    Returns:
        str: 格式化後的字串
    """
    try:
        if not domains:
            return "(無)"

        sorted_domains = sorted(domains)
        result = []
        current_length = 0

        for domain in sorted_domains:
            line = f"• {domain}"
            if current_length + len(line) + 1 > max_length:
                remaining = len(sorted_domains) - len(result)
                if remaining > 0:
                    result.append(f"... 還有 {remaining} 個網域")
                break

            result.append(line)
            current_length += len(line) + 1

        return "\n".join(result)
    except Exception:
        return "(解析錯誤)"


def get_config_description(key: str) -> str:
    """
    獲取配置項目的描述

    Args:
        key: 配置鍵名

    Returns:
        str: 配置描述
    """
    descriptions = {
        "enabled": "是否啟用反惡意連結保護",
        "whitelist": "白名單網域列表(以逗號分隔)",
        "blacklist": "手動黑名單網域列表(以逗號分隔)",
        "delete_message": "刪除惡意連結時顯示的訊息",
        "notify_channel": "管理員通知頻道 ID",
        "whitelist_admins": "是否將管理員加入白名單",
        "check_embeds": "是否檢查嵌入內容中的連結",
        "auto_update": "是否自動更新威脅情資",
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
        "links_blocked": "已阻止的惡意連結數量",
        "messages_deleted": "已刪除的訊息數量",
        "whitelist_hits": "白名單命中次數",
        "blacklist_hits": "黑名單命中次數",
        "remote_blacklist_hits": "遠端黑名單命中次數",
        "false_positives": "誤報次數",
        "manual_additions": "手動添加的黑名單項目",
        "manual_removals": "手動移除的黑名單項目",
    }

    return descriptions.get(key, "未知統計項目")
