"""
資料同步狀態嵌入組件
- 顯示當前同步狀態
- 顯示最後同步時間
- 顯示統計資訊
"""

import datetime as dt
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import SyncDataCog

# 時間常數定義
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
DAYS_THRESHOLD_FOR_OUTDATED = 7


async def create_status_embed(
    cog: "SyncDataCog", guild: discord.Guild
) -> discord.Embed:
    """
    創建同步狀態嵌入

    Args:
        cog: SyncDataCog 實例
        guild: Discord 伺服器物件

    Returns:
        discord.Embed: 狀態嵌入物件
    """
    embed = discord.Embed(
        title="📊 資料同步狀態",
        description=f"伺服器:**{guild.name}**",
        color=discord.Color.blue(),
    )

    try:
        # 獲取最後同步記錄
        last_sync = await cog.db.get_last_sync_record(guild.id)

        if last_sync:
            # 格式化時間
            sync_time = last_sync.get("start_time", last_sync.get("sync_start_time"))
            if sync_time:
                if isinstance(sync_time, str):
                    try:
                        # 嘗試解析不同的時間格式
                        if "T" in sync_time:
                            sync_time = dt.datetime.fromisoformat(
                                sync_time.replace("Z", "+00:00")
                            )
                        else:
                            sync_time = dt.datetime.strptime(
                                sync_time, "%Y-%m-%d %H:%M:%S"
                            )
                    except ValueError:
                        sync_time = dt.datetime.utcnow()
                elif not isinstance(sync_time, dt.datetime):
                    sync_time = dt.datetime.utcnow()
            else:
                sync_time = dt.datetime.utcnow()

            # 計算時間差
            now = dt.datetime.utcnow()
            time_ago = now - sync_time

            if time_ago.days > 0:
                time_str = f"{time_ago.days} 天前"
            elif time_ago.seconds > SECONDS_PER_HOUR:
                hours = time_ago.seconds // SECONDS_PER_HOUR
                time_str = f"{hours} 小時前"
            elif time_ago.seconds > SECONDS_PER_MINUTE:
                minutes = time_ago.seconds // SECONDS_PER_MINUTE
                time_str = f"{minutes} 分鐘前"
            else:
                time_str = "剛才"

            # 狀態圖標
            status_icon = "✅" if last_sync.get("status") == "success" else "❌"

            embed.add_field(
                name="🕒 最後同步",
                value=(
                    f"{status_icon} {time_str}\n"
                    f"類型:{_get_sync_type_name(last_sync.get('sync_type', 'unknown'))}\n"
                    f"耗時:{last_sync.get('duration', 0):.2f} 秒"
                ),
                inline=True,
            )

            # 同步結果
            roles_count = last_sync.get("roles_processed", 0)
            channels_count = last_sync.get("channels_processed", 0)

            embed.add_field(
                name="📈 同步結果",
                value=(
                    f"角色:{roles_count} 個\n"
                    f"頻道:{channels_count} 個\n"
                    f"狀態:{_get_status_name(last_sync.get('status', 'unknown'))}"
                ),
                inline=True,
            )
        else:
            embed.add_field(name="🕒 最後同步", value="尚未進行過同步", inline=True)

            embed.add_field(name="📈 同步結果", value="暫無資料", inline=True)

        # 當前伺服器統計
        embed.add_field(
            name="📊 伺服器資訊",
            value=(
                f"角色數量:{len(guild.roles)} 個\n"
                f"頻道數量:{len(guild.channels)} 個\n"
                f"成員數量:{guild.member_count} 人"
            ),
            inline=True,
        )

        # 資料庫統計
        try:
            db_roles = await cog.db.get_guild_roles(guild.id)
            db_channels = await cog.db.get_guild_channels(guild.id)

            embed.add_field(
                name="💾 資料庫資訊",
                value=(
                    f"已存角色:{len(db_roles)} 個\n"
                    f"已存頻道:{len(db_channels)} 個\n"
                    f"同步率:{_calculate_sync_rate(guild, db_roles, db_channels)}"
                ),
                inline=True,
            )
        except Exception:
            embed.add_field(name="💾 資料庫資訊", value="載入失敗", inline=True)

        # 建議操作
        if not last_sync:
            embed.add_field(
                name="💡 建議", value="建議執行一次完整同步來初始化資料", inline=False
            )
        elif last_sync.get("status") != "success":
            embed.add_field(
                name="💡 建議", value="上次同步失敗,建議重新執行同步", inline=False
            )
        elif time_ago.days > DAYS_THRESHOLD_FOR_OUTDATED:
            embed.add_field(
                name="💡 建議", value="資料已過期,建議執行同步更新", inline=False
            )

        # 設置時間戳
        embed.timestamp = dt.datetime.utcnow()
        embed.set_footer(text="點擊「刷新」更新資料")

    except Exception as e:
        embed.add_field(
            name="❌ 錯誤", value=f"載入狀態時發生錯誤:{str(e)[:100]}", inline=False
        )

    return embed


def _get_sync_type_name(sync_type: str) -> str:
    """獲取同步類型名稱"""
    type_names = {"full": "完整同步", "roles": "角色同步", "channels": "頻道同步"}
    return type_names.get(sync_type, "未知")


def _get_status_name(status: str) -> str:
    """獲取狀態名稱"""
    status_names = {"success": "成功", "failed": "失敗", "running": "進行中"}
    return status_names.get(status, "未知")


def _calculate_sync_rate(
    guild: discord.Guild, db_roles: list, db_channels: list
) -> str:
    """計算同步率"""
    try:
        role_rate = len(db_roles) / len(guild.roles) * 100 if guild.roles else 0
        channel_rate = (
            len(db_channels) / len(guild.channels) * 100 if guild.channels else 0
        )
        avg_rate = (role_rate + channel_rate) / 2
        return f"{avg_rate:.1f}%"
    except (ZeroDivisionError, TypeError, AttributeError):
        return "計算失敗"
