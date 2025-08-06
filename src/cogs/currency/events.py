"""Currency Event Definitions for Discord ROAS Bot v2.0.

此模組定義貨幣系統的事件 Payload 結構, 支援:
- 轉帳事件 (CurrencyTransferEvent)
- 餘額更新事件 (CurrencyBalanceUpdateEvent)
- 事件驗證和序列化
- JSON Schema 定義
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from jsonschema import Draft7Validator


class CurrencyEventType(Enum):
    """貨幣事件類型枚舉."""

    TRANSFER = "currency.transfer"
    BALANCE_UPDATE = "currency.balance_update"


@dataclass
class CurrencyTransferEvent:
    """貨幣轉帳事件.

    當用戶之間發生轉帳時觸發, 包含完整的交易資訊.

    Attributes:
        transaction_id: 唯一交易 ID
        guild_id: Discord 伺服器 ID
        from_user_id: 轉出用戶 Discord ID
        to_user_id: 轉入用戶 Discord ID
        amount: 轉帳金額(正數)
        from_balance_after: 轉出用戶轉帳後餘額
        to_balance_after: 轉入用戶轉帳後餘額
        reason: 轉帳原因(可選)
        admin_initiated: 是否為管理員發起的轉帳
        timestamp: 事件發生時間戳(ISO 格式)
        metadata: 額外的事件元資料(可選)
    """

    transaction_id: str
    guild_id: int
    from_user_id: int
    to_user_id: int
    amount: int
    from_balance_after: int
    to_balance_after: int
    timestamp: str
    reason: str | None = None
    admin_initiated: bool = False
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式."""
        return asdict(self)

    def to_json(self) -> str:
        """轉換為 JSON 字串."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurrencyTransferEvent:
        """從字典建立事件實例."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> CurrencyTransferEvent:
        """從 JSON 字串建立事件實例."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def validate(self) -> bool:
        """驗證事件資料的有效性."""
        return validate_currency_transfer_event(self.to_dict())


@dataclass
class CurrencyBalanceUpdateEvent:
    """貨幣餘額更新事件.

    當用戶餘額發生變化時觸發, 用於通知其他系統模組.

    Attributes:
        guild_id: Discord 伺服器 ID
        user_id: 用戶 Discord ID
        delta: 餘額變化量(正數為增加, 負數為減少)
        balance_after: 更新後的餘額
        trigger_type: 觸發類型(transfer、admin_adjustment、reward 等)
        trigger_id: 觸發事件的 ID(如轉帳的 transaction_id)
        timestamp: 事件發生時間戳(ISO 格式)
        metadata: 額外的事件元資料(可選)
    """

    guild_id: int
    user_id: int
    delta: int
    balance_after: int
    timestamp: str
    trigger_type: str = "unknown"
    trigger_id: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式."""
        return asdict(self)

    def to_json(self) -> str:
        """轉換為 JSON 字串."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurrencyBalanceUpdateEvent:
        """從字典建立事件實例."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> CurrencyBalanceUpdateEvent:
        """從 JSON 字串建立事件實例."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def validate(self) -> bool:
        """驗證事件資料的有效性."""
        return validate_currency_balance_update_event(self.to_dict())


# JSON Schema 定義
CURRENCY_TRANSFER_EVENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CurrencyTransferEvent",
    "description": "貨幣轉帳事件的資料結構",
    "type": "object",
    "properties": {
        "transaction_id": {
            "type": "string",
            "description": "唯一交易 ID",
            "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        },
        "guild_id": {
            "type": "integer",
            "description": "Discord 伺服器 ID",
            "minimum": 1,
        },
        "from_user_id": {
            "type": "integer",
            "description": "轉出用戶 Discord ID",
            "minimum": 1,
        },
        "to_user_id": {
            "type": "integer",
            "description": "轉入用戶 Discord ID",
            "minimum": 1,
        },
        "amount": {
            "type": "integer",
            "description": "轉帳金額",
            "minimum": 1,
            "maximum": 1152921504606846976,  # 2^60
        },
        "from_balance_after": {
            "type": "integer",
            "description": "轉出用戶轉帳後餘額",
            "minimum": 0,
        },
        "to_balance_after": {
            "type": "integer",
            "description": "轉入用戶轉帳後餘額",
            "minimum": 0,
        },
        "timestamp": {
            "type": "string",
            "description": "事件發生時間戳(ISO 格式)",
            "format": "date-time",
        },
        "reason": {
            "type": ["string", "null"],
            "description": "轉帳原因",
            "maxLength": 500,
        },
        "admin_initiated": {
            "type": "boolean",
            "description": "是否為管理員發起的轉帳",
            "default": False,
        },
        "metadata": {
            "type": ["object", "null"],
            "description": "額外的事件元資料",
            "additionalProperties": True,
        },
    },
    "required": [
        "transaction_id",
        "guild_id",
        "from_user_id",
        "to_user_id",
        "amount",
        "from_balance_after",
        "to_balance_after",
        "timestamp",
    ],
    "additionalProperties": False,
}

CURRENCY_BALANCE_UPDATE_EVENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CurrencyBalanceUpdateEvent",
    "description": "貨幣餘額更新事件的資料結構",
    "type": "object",
    "properties": {
        "guild_id": {
            "type": "integer",
            "description": "Discord 伺服器 ID",
            "minimum": 1,
        },
        "user_id": {"type": "integer", "description": "用戶 Discord ID", "minimum": 1},
        "delta": {
            "type": "integer",
            "description": "餘額變化量(正數為增加, 負數為減少)",
        },
        "balance_after": {
            "type": "integer",
            "description": "更新後的餘額",
            "minimum": 0,
        },
        "timestamp": {
            "type": "string",
            "description": "事件發生時間戳(ISO 格式)",
            "format": "date-time",
        },
        "trigger_type": {
            "type": "string",
            "description": "觸發類型",
            "enum": [
                "transfer",
                "admin_adjustment",
                "reward",
                "penalty",
                "system",
                "unknown",
            ],
            "default": "unknown",
        },
        "trigger_id": {"type": ["string", "null"], "description": "觸發事件的 ID"},
        "metadata": {
            "type": ["object", "null"],
            "description": "額外的事件元資料",
            "additionalProperties": True,
        },
    },
    "required": ["guild_id", "user_id", "delta", "balance_after", "timestamp"],
    "additionalProperties": False,
}


def validate_currency_transfer_event(data: dict[str, Any]) -> bool:
    """驗證轉帳事件資料.

    Args:
        data: 事件資料字典

    Returns:
        是否通過驗證

    Raises:
        ValidationError: 當資料不符合 Schema 時
    """
    validator = Draft7Validator(CURRENCY_TRANSFER_EVENT_SCHEMA)
    validator.validate(data)
    return True


def validate_currency_balance_update_event(data: dict[str, Any]) -> bool:
    """驗證餘額更新事件資料.

    Args:
        data: 事件資料字典

    Returns:
        是否通過驗證

    Raises:
        ValidationError: 當資料不符合 Schema 時
    """
    validator = Draft7Validator(CURRENCY_BALANCE_UPDATE_EVENT_SCHEMA)
    validator.validate(data)
    return True


def create_transfer_event(
    transaction_id: str,
    guild_id: int,
    from_user_id: int,
    to_user_id: int,
    amount: int,
    from_balance_after: int,
    to_balance_after: int,
    reason: str | None = None,
    admin_initiated: bool = False,
    metadata: dict[str, Any] | None = None,
) -> CurrencyTransferEvent:
    """建立轉帳事件實例.

    便利函數, 自動設定時間戳並驗證資料.

    Args:
        transaction_id: 交易 ID
        guild_id: Discord 伺服器 ID
        from_user_id: 轉出用戶 ID
        to_user_id: 轉入用戶 ID
        amount: 轉帳金額
        from_balance_after: 轉出用戶轉帳後餘額
        to_balance_after: 轉入用戶轉帳後餘額
        reason: 轉帳原因
        admin_initiated: 是否為管理員發起
        metadata: 額外元資料

    Returns:
        轉帳事件實例

    Raises:
        ValidationError: 當資料不符合要求時
    """
    event = CurrencyTransferEvent(
        transaction_id=transaction_id,
        guild_id=guild_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount=amount,
        from_balance_after=from_balance_after,
        to_balance_after=to_balance_after,
        timestamp=datetime.utcnow().isoformat() + "Z",
        reason=reason,
        admin_initiated=admin_initiated,
        metadata=metadata,
    )

    # 驗證事件資料
    event.validate()
    return event


def create_balance_update_event(
    guild_id: int,
    user_id: int,
    delta: int,
    balance_after: int,
    trigger_type: str = "unknown",
    trigger_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CurrencyBalanceUpdateEvent:
    """建立餘額更新事件實例.

    便利函數, 自動設定時間戳並驗證資料.

    Args:
        guild_id: Discord 伺服器 ID
        user_id: 用戶 ID
        delta: 餘額變化量
        balance_after: 更新後餘額
        trigger_type: 觸發類型
        trigger_id: 觸發事件 ID
        metadata: 額外元資料

    Returns:
        餘額更新事件實例

    Raises:
        ValidationError: 當資料不符合要求時
    """
    event = CurrencyBalanceUpdateEvent(
        guild_id=guild_id,
        user_id=user_id,
        delta=delta,
        balance_after=balance_after,
        timestamp=datetime.utcnow().isoformat() + "Z",
        trigger_type=trigger_type,
        trigger_id=trigger_id,
        metadata=metadata,
    )

    # 驗證事件資料
    event.validate()
    return event


__all__ = [
    "CURRENCY_BALANCE_UPDATE_EVENT_SCHEMA",
    "CURRENCY_TRANSFER_EVENT_SCHEMA",
    "CurrencyBalanceUpdateEvent",
    "CurrencyEventType",
    "CurrencyTransferEvent",
    "create_balance_update_event",
    "create_transfer_event",
    "validate_currency_balance_update_event",
    "validate_currency_transfer_event",
]
