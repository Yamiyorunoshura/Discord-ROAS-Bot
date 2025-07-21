# Discord ADR Bot v1.6 - 代碼風格和約定

## 代碼風格

### 格式化工具
- **Black** - 自動代碼格式化
- **flake8** - 代碼風格檢查
- **mypy** - 靜態類型檢查

### 命名約定
- **檔案名稱**：snake_case（例：`main.py`, `database.py`）
- **類別名稱**：PascalCase（例：`ActivityMeter`, `WelcomeCog`）
- **函數和變數**：snake_case（例：`get_user_data`, `activity_score`）
- **常數**：UPPER_CASE（例：`MAX_SCORE`, `DEFAULT_TIMEOUT`）

### 模組結構
每個功能模組遵循標準結構：
```
cogs/module_name/
├── __init__.py          # 模組入口
├── main/
│   ├── __init__.py
│   ├── main.py          # 主要邏輯
│   ├── calculator.py    # 計算邏輯
│   └── tasks.py         # 背景任務
├── panel/
│   ├── __init__.py
│   ├── main_view.py     # 主要視圖
│   ├── components/      # UI 組件
│   └── embeds/          # 嵌入訊息
├── config/
│   ├── __init__.py
│   └── config.py        # 配置設定
└── database/
    ├── __init__.py
    └── database.py      # 資料庫操作
```

## 文檔字符串

### 函數文檔
```python
def calculate_activity_score(user_id: int, days: int = 7) -> float:
    """
    計算用戶活躍度分數
    
    參數：
        user_id (int): 用戶 ID
        days (int): 計算天數，預設 7 天
    
    回傳：
        float: 活躍度分數（0-100）
    
    異常：
        ValueError: 當 days 小於 1 時拋出
        DatabaseError: 資料庫查詢失敗時拋出
    """
```

### 類別文檔
```python
class ActivityMeter(commands.Cog):
    """
    活躍度系統核心類別
    
    功能：
    - 追蹤用戶活躍度
    - 生成排行榜
    - 自動播報系統
    
    屬性：
        bot: Discord 機器人實例
        db: 資料庫連線
        cache: 快取管理器
    """
```

## 類型提示

### 基本類型
```python
from typing import Optional, List, Dict, Any, Union
import discord
from discord.ext import commands

async def get_user_data(
    user_id: int,
    guild_id: Optional[int] = None
) -> Dict[str, Any]:
    """取得用戶資料"""
```

### Discord 類型
```python
async def send_message(
    channel: discord.TextChannel,
    content: str,
    embed: Optional[discord.Embed] = None
) -> discord.Message:
    """發送訊息"""
```

## 錯誤處理

### 異常處理模式
```python
import logging
from cogs.core.error_handler import error_handler

logger = logging.getLogger(__name__)

@error_handler
async def risky_operation():
    """具有錯誤處理的操作"""
    try:
        # 執行操作
        result = await some_operation()
        return result
    except SpecificError as e:
        logger.error(f"特定錯誤: {e}")
        raise
    except Exception as e:
        logger.exception(f"未預期錯誤: {e}")
        raise
```

### 互動錯誤處理
```python
from cogs.core.base_cog import BaseCog

class MyCog(BaseCog):
    @discord.app_commands.command()
    async def my_command(self, interaction: discord.Interaction):
        """指令實現"""
        try:
            await interaction.response.defer()
            # 執行邏輯
            await interaction.followup.send("完成")
        except Exception as e:
            await self.handle_interaction_error(interaction, e)
```

## 日誌記錄

### 日誌設定
```python
import logging
from cogs.core.logger import setup_module_logger

logger = setup_module_logger(__name__)

# 使用範例
logger.info("操作開始")
logger.warning("警告訊息")
logger.error("錯誤訊息")
logger.exception("異常訊息")  # 包含堆疊追蹤
```

### 日誌格式
- 時間戳：`YYYY-MM-DD HH:MM:SS`
- 等級：`INFO`, `WARNING`, `ERROR`, `DEBUG`
- 訊息：中文描述，包含相關上下文

## 資料庫操作

### 連線管理
```python
from cogs.core.database_pool import get_global_pool

async def database_operation():
    """資料庫操作範例"""
    pool = get_global_pool()
    async with pool.acquire() as conn:
        await conn.execute("SELECT * FROM users")
```

### 異步操作
```python
import aiosqlite
from typing import List, Tuple

async def batch_insert(
    data: List[Tuple[Any, ...]]
) -> None:
    """批量插入資料"""
    async with aiosqlite.connect("database.db") as db:
        await db.executemany(
            "INSERT INTO table (col1, col2) VALUES (?, ?)",
            data
        )
        await db.commit()
```

## 配置管理

### 環境變數
```python
import os
from dotenv import load_dotenv

load_dotenv()

# 必要配置
TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

# 可選配置
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
```

### 配置檔案
```python
# config.py
from datetime import timezone, timedelta

# 時區設定
TW_TZ = timezone(timedelta(hours=8))

# 活躍度系統設定
ACTIVITY_MAX_SCORE = 100
ACTIVITY_GAIN = 0.5
ACTIVITY_COOLDOWN = 60
```

## 測試約定

### 測試結構
```
tests/
├── unit/           # 單元測試
├── integration/    # 整合測試
├── performance/    # 效能測試
└── conftest.py     # 測試配置
```

### 測試命名
```python
import pytest
from unittest.mock import AsyncMock

class TestActivityMeter:
    """活躍度系統測試"""
    
    async def test_calculate_score_valid_input(self):
        """測試有效輸入的分數計算"""
        
    async def test_calculate_score_invalid_input(self):
        """測試無效輸入的錯誤處理"""
```