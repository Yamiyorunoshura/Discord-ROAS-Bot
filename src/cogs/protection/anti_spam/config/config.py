"""
反垃圾訊息保護模組配置
- 定義所有常數和預設值
- 配置結構定義
- 工具函數
"""

from difflib import SequenceMatcher
from typing import Any

# ────────────────────────────
# 預設配置值
# ────────────────────────────
DEFAULTS = {
    "spam_freq_limit": 5,  # 頻率限制(訊息數)
    "spam_freq_window": 10,  # 頻率窗口(秒)
    "spam_identical_limit": 3,  # 重複訊息限制
    "spam_identical_window": 30,  # 重複窗口(秒)
    "spam_similar_limit": 3,  # 相似訊息限制
    "spam_similar_window": 60,  # 相似窗口(秒)
    "spam_similar_threshold": 0.8,  # 相似度閾值
    "spam_sticker_limit": 5,  # 貼圖限制
    "spam_sticker_window": 30,  # 貼圖窗口(秒)
    "spam_timeout_minutes": 5,  # 違規超時(分鐘)
    "spam_notify_channel": "",  # 通知頻道 ID
    "spam_response_message": "您已觸發洗版限制,請注意您的行為.",  # 自定義回復訊息
    "spam_response_enabled": "true",  # 是否啟用自定義回復
}

# ────────────────────────────
# 配置項中文名稱
# ────────────────────────────
CH_NAMES = {
    "spam_freq_limit": "頻率限制",
    "spam_freq_window": "頻率窗口",
    "spam_identical_limit": "重複限制",
    "spam_identical_window": "重複窗口",
    "spam_similar_limit": "相似限制",
    "spam_similar_window": "相似窗口",
    "spam_similar_threshold": "相似度閾值",
    "spam_sticker_limit": "貼圖限制",
    "spam_sticker_window": "貼圖窗口",
    "spam_timeout_minutes": "超時分鐘",
    "spam_notify_channel": "通知頻道",
    "spam_response_message": "回復訊息",
    "spam_response_enabled": "啟用回復",
}

# ────────────────────────────
# 進階配置結構
# ────────────────────────────
CONFIG_CATEGORIES = {
    "frequency": {
        "name": "洗版頻率",
        "desc": "設定訊息頻率限制,防止短時間內發送大量訊息",
        "items": [
            {
                "key": "spam_freq_limit",
                "name": "頻率限制",
                "desc": "在指定時間窗口內,超過此數量的訊息將被視為洗版",
                "recommend": "5-8 (一般伺服器) / 3-5 (嚴格模式)",
                "type": "int",
            },
            {
                "key": "spam_freq_window",
                "name": "頻率窗口",
                "desc": "檢查洗版行為的時間窗口(秒)",
                "recommend": "10-15 秒",
                "type": "int",
            },
        ],
    },
    "repeat": {
        "name": "重複/相似訊息",
        "desc": "設定重複或相似內容的訊息限制",
        "items": [
            {
                "key": "spam_identical_limit",
                "name": "重複限制",
                "desc": "在指定時間內,發送相同訊息超過此數量將被視為洗版",
                "recommend": "3 次",
                "type": "int",
            },
            {
                "key": "spam_identical_window",
                "name": "重複窗口",
                "desc": "檢查重複訊息的時間窗口(秒)",
                "recommend": "30-60 秒",
                "type": "int",
            },
            {
                "key": "spam_similar_limit",
                "name": "相似限制",
                "desc": "在指定時間內,發送相似訊息超過此數量將被視為洗版",
                "recommend": "3-5 次",
                "type": "int",
            },
            {
                "key": "spam_similar_window",
                "name": "相似窗口",
                "desc": "檢查相似訊息的時間窗口(秒)",
                "recommend": "60-120 秒",
                "type": "int",
            },
            {
                "key": "spam_similar_threshold",
                "name": "相似度閾值",
                "desc": "判定訊息相似的閾值(0-1之間的小數,越大表示越相似)",
                "recommend": "0.7-0.8",
                "type": "float",
            },
        ],
    },
    "sticker": {
        "name": "貼圖限制",
        "desc": "設定貼圖使用頻率限制",
        "items": [
            {
                "key": "spam_sticker_limit",
                "name": "貼圖限制",
                "desc": "在指定時間內,發送貼圖超過此數量將被視為濫用",
                "recommend": "5-8 次",
                "type": "int",
            },
            {
                "key": "spam_sticker_window",
                "name": "貼圖窗口",
                "desc": "檢查貼圖使用的時間窗口(秒)",
                "recommend": "30-60 秒",
                "type": "int",
            },
        ],
    },
    "action": {
        "name": "處理動作",
        "desc": "設定對洗版行為的處理方式",
        "items": [
            {
                "key": "spam_timeout_minutes",
                "name": "超時分鐘",
                "desc": "觸發洗版保護時,禁言的時間長度(分鐘)",
                "recommend": "3-10 分鐘",
                "type": "int",
            },
            {
                "key": "spam_notify_channel",
                "name": "通知頻道",
                "desc": "洗版事件的通知頻道ID(輸入頻道ID或none來清除)",
                "recommend": "管理頻道ID",
                "type": "channel",
            },
            {
                "key": "spam_response_enabled",
                "name": "啟用回復",
                "desc": "是否在用戶觸發洗版限制時發送回復訊息",
                "recommend": "true 或 false",
                "type": "bool",
            },
            {
                "key": "spam_response_message",
                "name": "回復訊息",
                "desc": "當用戶觸發洗版限制時的回復訊息",
                "recommend": "自訂警告文字",
                "type": "str",
            },
        ],
    },
}

# ────────────────────────────
# 配置項反向映射
# ────────────────────────────
CONFIG_KEY_MAP = {}
for category_id, category in CONFIG_CATEGORIES.items():
    for item in category["items"]:
        CONFIG_KEY_MAP[item["key"]] = {"category": category_id, "item": item}


# ────────────────────────────
# 工具函數
# ────────────────────────────
def calculate_similarity(text1: str, text2: str) -> float:
    """
    計算兩個字串的相似度

    Args:
        text1: 第一個字串
        text2: 第二個字串

    Returns:
        float: 相似度(0-1之間)
    """
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def get_config_display_name(key: str) -> str:
    """
    取得配置項的顯示名稱

    Args:
        key: 配置鍵名

    Returns:
        str: 顯示名稱
    """
    return CH_NAMES.get(key, key)


def get_config_category(key: str) -> dict[str, Any]:
    """
    取得配置項所屬的分類

    Args:
        key: 配置鍵名

    Returns:
        Dict[str, Any]: 分類資訊
    """
    return CONFIG_KEY_MAP.get(key, {})


def get_default_value(key: str) -> Any:
    """
    取得配置項的預設值

    Args:
        key: 配置鍵名

    Returns:
        Any: 預設值
    """
    return DEFAULTS.get(key)


def validate_config_value(key: str, value: str) -> tuple[bool, str]:
    """
    驗證配置值是否有效

    Args:
        key: 配置鍵名
        value: 配置值

    Returns:
        Tuple[bool, str]: (是否有效, 錯誤訊息)
    """
    config_info = CONFIG_KEY_MAP.get(key)
    if not config_info:
        return False, "未知的配置項"

    config_type = config_info["item"]["type"]

    try:
        if config_type == "int":
            int_value = int(value)
            if int_value < 0:
                return False, "數值不能為負數"
        elif config_type == "float":
            float_value = float(value)
            if float_value < 0 or float_value > 1:
                return False, "數值必須在 0-1 之間"
        elif config_type == "bool":
            if value.lower() not in ["true", "false"]:
                return False, "布林值必須是 true 或 false"
        elif config_type == "channel":
            if value.lower() != "none" and not value.isdigit():
                return False, "頻道ID必須是數字或 'none'"
        # str 類型不需要特別驗證

        return True, ""

    except ValueError:
        return False, f"無法轉換為 {config_type} 類型"
