"""
資料同步歷史記錄嵌入組件
- 顯示同步歷史記錄
- 顯示詳細的同步結果
- 提供分頁功能
"""

import datetime as dt
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from ...main.main import SyncDataCog


async def create_history_embed(
    cog: "SyncDataCog", guild: discord.Guild, page: int = 0
) -> discord.Embed:
    """
    創建同步歷史記錄嵌入

    Args:
        cog: SyncDataCog 實例
        guild: Discord 伺服器物件
        page: 頁碼

    Returns:
        discord.Embed: 歷史記錄嵌入物件
    """
    embed = discord.Embed(
        title="📋 同步歷史記錄",
        description=f"伺服器:**{guild.name}**",
        color=discord.Color.green(),
    )

    try:
        # 獲取歷史記錄 (暫時使用模擬資料)
        history_records = await _get_sync_history(cog, guild.id, page)

        if not history_records:
            embed.add_field(name="📝 記錄", value="暫無同步歷史記錄", inline=False)
        else:
            # 顯示記錄
            for i, record in enumerate(history_records[:5], 1):
                status_icon = "✅" if record.get("status") == "success" else "❌"
                sync_type = _get_sync_type_name(record.get("sync_type", "unknown"))

                # 格式化時間
                sync_time = record.get("sync_start_time", dt.datetime.utcnow())
                if isinstance(sync_time, str):
                    try:
                        sync_time = dt.datetime.fromisoformat(
                            sync_time.replace("Z", "+00:00")
                        )
                    except:
                        sync_time = dt.datetime.utcnow()

                time_str = sync_time.strftime("%m/%d %H:%M")

                # 結果統計
                roles_count = record.get("roles_processed", 0)
                channels_count = record.get("channels_processed", 0)
                duration = record.get("duration", 0)

                value = (
                    f"{status_icon} **{sync_type}** - {time_str}\n"
                    f"角色:{roles_count} | 頻道:{channels_count}\n"
                    f"耗時:{duration:.2f}秒"
                )

                if record.get("error_message"):
                    value += f"\n❌ {record['error_message'][:50]}..."

                embed.add_field(name=f"#{i + page * 5}", value=value, inline=True)

        # 統計資訊
        total_syncs = await _get_total_sync_count(cog, guild.id)
        success_syncs = await _get_success_sync_count(cog, guild.id)
        success_rate = (success_syncs / total_syncs * 100) if total_syncs > 0 else 0

        embed.add_field(
            name="📊 統計資訊",
            value=(
                f"總同步次數:{total_syncs}\n"
                f"成功次數:{success_syncs}\n"
                f"成功率:{success_rate:.1f}%"
            ),
            inline=False,
        )

        # 分頁資訊
        total_pages = (total_syncs + 4) // 5  # 每頁5條記錄
        if total_pages > 1:
            embed.set_footer(
                text=f"第 {page + 1}/{total_pages} 頁 | 點擊「刷新」更新資料"
            )
        else:
            embed.set_footer(text="點擊「刷新」更新資料")

        embed.timestamp = dt.datetime.utcnow()

    except Exception as e:
        embed.add_field(
            name="❌ 錯誤",
            value=f"載入歷史記錄時發生錯誤:{str(e)[:100]}",
            inline=False,
        )

    return embed


async def _get_sync_history(
    cog: "SyncDataCog", guild_id: int, page: int = 0
) -> list[dict[str, Any]]:
    """
    獲取同步歷史記錄

    Args:
        cog: SyncDataCog 實例
        guild_id: 伺服器 ID
        page: 頁碼

    Returns:
        List[Dict[str, Any]]: 歷史記錄列表
    """
    try:
        # 這裡應該調用資料庫方法獲取歷史記錄
        # 暫時返回模擬資料
        mock_records = [
            {
                "sync_type": "full",
                "status": "success",
                "sync_start_time": dt.datetime.utcnow() - dt.timedelta(hours=2),
                "roles_processed": 15,
                "channels_processed": 8,
                "duration": 3.45,
                "error_message": None,
            },
            {
                "sync_type": "roles",
                "status": "success",
                "sync_start_time": dt.datetime.utcnow() - dt.timedelta(days=1),
                "roles_processed": 15,
                "channels_processed": 0,
                "duration": 1.23,
                "error_message": None,
            },
            {
                "sync_type": "channels",
                "status": "failed",
                "sync_start_time": dt.datetime.utcnow() - dt.timedelta(days=2),
                "roles_processed": 0,
                "channels_processed": 0,
                "duration": 0.56,
                "error_message": "網絡連接超時",
            },
        ]

        start_idx = page * 5
        end_idx = start_idx + 5
        return mock_records[start_idx:end_idx]

    except Exception:
        return []


async def _get_total_sync_count(cog: "SyncDataCog", guild_id: int) -> int:
    """獲取總同步次數"""
    try:
        # 這裡應該調用資料庫方法
        return 3  # 模擬資料
    except Exception:
        return 0


async def _get_success_sync_count(cog: "SyncDataCog", guild_id: int) -> int:
    """獲取成功同步次數"""
    try:
        # 這裡應該調用資料庫方法
        return 2  # 模擬資料
    except Exception:
        return 0


def _get_sync_type_name(sync_type: str) -> str:
    """獲取同步類型名稱"""
    type_names = {"full": "完整同步", "roles": "角色同步", "channels": "頻道同步"}
    return type_names.get(sync_type, "未知")
