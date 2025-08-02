"""成就進度追蹤服務.

此模組實作成就進度追蹤系統，提供：
- 用戶成就進度更新和計算
- 進度驗證和邊界檢查
- 批量進度更新處理
- 進度歷史追蹤和分析
- 自動成就完成檢測

進度追蹤器遵循以下設計原則：
- 支援多種成就類型的進度計算
- 提供原子性的進度更新操作
- 整合業務規則驗證和邏輯檢查
- 支援複雜進度資料結構的處理
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..database.models import (
    Achievement,
    AchievementProgress,
    AchievementType,
)

if TYPE_CHECKING:
    from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)


class ProgressTracker:
    """成就進度追蹤服務.

    提供成就進度追蹤和更新的核心功能，包含：
    - 進度更新和計算邏輯
    - 自動成就完成檢測
    - 批量進度更新處理
    - 進度驗證和邊界檢查
    """

    def __init__(self, repository: AchievementRepository):
        """初始化進度追蹤器.

        Args:
            repository: 成就資料存取庫
        """
        self._repository = repository

        logger.info("ProgressTracker 初始化完成")

    async def __aenter__(self) -> ProgressTracker:
        """異步上下文管理器進入."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        pass

    # =============================================================================
    # 進度更新核心邏輯
    # =============================================================================

    async def update_user_progress(
        self,
        user_id: int,
        achievement_id: int,
        increment_value: float = 1.0,
        progress_data: dict[str, Any] | None = None,
        force_value: float | None = None
    ) -> AchievementProgress:
        """更新用戶成就進度.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            increment_value: 進度增量值（預設 1.0）
            progress_data: 額外的進度資料
            force_value: 強制設定的進度值（覆蓋增量）

        Returns:
            更新後的進度記錄

        Raises:
            ValueError: 成就不存在或參數無效
        """
        # 驗證成就是否存在且啟用
        achievement = await self._repository.get_achievement_by_id(achievement_id)
        if not achievement:
            raise ValueError(f"成就 {achievement_id} 不存在")

        if not achievement.is_active:
            logger.warning(
                "嘗試更新非啟用成就的進度",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id
                }
            )
            raise ValueError(f"成就 {achievement_id} 未啟用")

        try:
            # 取得當前進度
            current_progress = await self._repository.get_user_progress(user_id, achievement_id)

            # 計算新的進度值
            if force_value is not None:
                new_value = force_value
            else:
                current_value = current_progress.current_value if current_progress else 0.0
                new_value = current_value + increment_value

            # 確保進度值不為負數
            new_value = max(0.0, new_value)

            # 合併進度資料
            merged_progress_data = self._merge_progress_data(
                existing_data=current_progress.progress_data if current_progress else None,
                new_data=progress_data,
                achievement_type=achievement.type
            )

            # 更新進度
            updated_progress = await self._repository.update_progress(
                user_id=user_id,
                achievement_id=achievement_id,
                current_value=new_value,
                progress_data=merged_progress_data
            )

            logger.info(
                "用戶成就進度更新成功",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "achievement_name": achievement.name,
                    "old_value": current_progress.current_value if current_progress else 0.0,
                    "new_value": new_value,
                    "is_completed": updated_progress.is_completed
                }
            )

            return updated_progress

        except Exception as e:
            logger.error(
                "用戶成就進度更新失敗",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "increment_value": increment_value,
                    "force_value": force_value,
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _merge_progress_data(
        self,
        existing_data: dict[str, Any] | None,
        new_data: dict[str, Any] | None,
        achievement_type: AchievementType
    ) -> dict[str, Any] | None:
        """合併進度資料.

        Args:
            existing_data: 現有進度資料
            new_data: 新的進度資料
            achievement_type: 成就類型

        Returns:
            合併後的進度資料
        """
        if not new_data:
            return existing_data

        if not existing_data:
            merged_data = new_data.copy()
        else:
            merged_data = existing_data.copy()
            merged_data.update(new_data)

        # 添加通用的追蹤資料
        merged_data["last_update_timestamp"] = datetime.now().isoformat()

        # 根據成就類型添加特定的追蹤邏輯
        if achievement_type == AchievementType.TIME_BASED:
            # 時間型成就需要追蹤連續性
            self._update_time_based_data(merged_data)
        elif achievement_type == AchievementType.COUNTER:
            # 計數型成就需要追蹤累積統計
            self._update_counter_data(merged_data)

        return merged_data

    def _update_time_based_data(self, progress_data: dict[str, Any]) -> None:
        """更新時間型成就的進度資料.

        Args:
            progress_data: 進度資料字典（會被直接修改）
        """
        current_date = datetime.now().date().isoformat()

        # 更新連續天數邏輯
        if "streak_dates" not in progress_data:
            progress_data["streak_dates"] = [current_date]
        else:
            streak_dates = progress_data["streak_dates"]
            if current_date not in streak_dates:
                streak_dates.append(current_date)
                # 保持最近 30 天的記錄
                progress_data["streak_dates"] = streak_dates[-30:]

    def _update_counter_data(self, progress_data: dict[str, Any]) -> None:
        """更新計數型成就的進度資料.

        Args:
            progress_data: 進度資料字典（會被直接修改）
        """
        current_date = datetime.now().date().isoformat()

        # 更新每日統計
        if "daily_counts" not in progress_data:
            progress_data["daily_counts"] = {}

        daily_counts = progress_data["daily_counts"]
        if current_date not in daily_counts:
            daily_counts[current_date] = 0
        daily_counts[current_date] += 1

    # =============================================================================
    # 批量進度更新
    # =============================================================================

    async def batch_update_progress(
        self,
        progress_updates: list[tuple[int, int, float, dict[str, Any]]]
    ) -> list[AchievementProgress]:
        """批量更新用戶成就進度.

        Args:
            progress_updates: (用戶ID, 成就ID, 增量值, 進度資料) 的元組列表

        Returns:
            更新後的進度記錄列表

        Raises:
            ValueError: 任何更新參數無效
        """
        if not progress_updates:
            return []

        updated_progresses = []
        errors = []

        for user_id, achievement_id, increment_value, progress_data in progress_updates:
            try:
                progress = await self.update_user_progress(
                    user_id=user_id,
                    achievement_id=achievement_id,
                    increment_value=increment_value,
                    progress_data=progress_data
                )
                updated_progresses.append(progress)
            except Exception as e:
                errors.append(
                    f"更新用戶 {user_id} 成就 {achievement_id} 進度失敗: {e!s}"
                )

        if errors:
            logger.warning(
                "批量進度更新部分失敗",
                extra={
                    "total": len(progress_updates),
                    "success": len(updated_progresses),
                    "errors": errors
                }
            )

        logger.info(
            "批量進度更新完成",
            extra={
                "total": len(progress_updates),
                "success": len(updated_progresses),
                "failed": len(errors)
            }
        )

        return updated_progresses

    # =============================================================================
    # 進度計算和驗證
    # =============================================================================

    async def calculate_achievement_progress(
        self,
        user_id: int,
        achievement: Achievement,
        current_metrics: dict[str, Any]
    ) -> float:
        """計算用戶對特定成就的進度值.

        Args:
            user_id: 用戶 ID
            achievement: 成就物件
            current_metrics: 用戶當前指標資料

        Returns:
            計算出的進度值

        Raises:
            ValueError: 成就類型不支援或參數無效
        """
        achievement_type = achievement.type
        criteria = achievement.criteria

        try:
            if achievement_type == AchievementType.COUNTER:
                return await self._calculate_counter_progress(
                    user_id, criteria, current_metrics
                )
            elif achievement_type == AchievementType.MILESTONE:
                return await self._calculate_milestone_progress(
                    user_id, criteria, current_metrics
                )
            elif achievement_type == AchievementType.TIME_BASED:
                return await self._calculate_time_based_progress(
                    user_id, achievement.id, criteria
                )
            elif achievement_type == AchievementType.CONDITIONAL:
                return await self._calculate_conditional_progress(
                    user_id, criteria, current_metrics
                )
            else:
                raise ValueError(f"不支援的成就類型: {achievement_type}")

        except Exception as e:
            logger.error(
                "計算成就進度失敗",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement.id,
                    "achievement_type": achievement_type.value,
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    async def _calculate_counter_progress(
        self,
        user_id: int,
        criteria: dict[str, Any],
        current_metrics: dict[str, Any]
    ) -> float:
        """計算計數型成就進度."""
        counter_field = criteria.get("counter_field")
        if not counter_field:
            raise ValueError("計數型成就缺少 counter_field")

        return float(current_metrics.get(counter_field, 0))

    async def _calculate_milestone_progress(
        self,
        user_id: int,
        criteria: dict[str, Any],
        current_metrics: dict[str, Any]
    ) -> float:
        """計算里程碑型成就進度."""
        milestone_type = criteria.get("milestone_type")
        if not milestone_type:
            raise ValueError("里程碑型成就缺少 milestone_type")

        # 根據里程碑類型取得對應的指標值
        metric_value = current_metrics.get(milestone_type, 0)
        return float(metric_value)

    async def _calculate_time_based_progress(
        self,
        user_id: int,
        achievement_id: int,
        criteria: dict[str, Any]
    ) -> float:
        """計算時間型成就進度."""
        # 取得現有進度資料
        progress = await self._repository.get_user_progress(user_id, achievement_id)
        if not progress or not progress.progress_data:
            return 0.0

        streak_dates = progress.progress_data.get("streak_dates", [])
        time_unit = criteria.get("time_unit", "days")

        if time_unit == "days":
            # 計算連續天數
            return float(self._calculate_consecutive_days(streak_dates))
        else:
            # 其他時間單位的邏輯
            return float(len(streak_dates))

    def _calculate_consecutive_days(self, streak_dates: list[str]) -> int:
        """計算連續天數.

        Args:
            streak_dates: 日期字串列表（ISO 格式）

        Returns:
            連續天數
        """
        if not streak_dates:
            return 0

        # 轉換為日期物件並排序
        dates = [datetime.fromisoformat(date).date() for date in streak_dates]
        dates.sort(reverse=True)

        # 計算從今天開始的連續天數
        today = datetime.now().date()
        consecutive_days = 0

        for i, date in enumerate(dates):
            expected_date = today - timedelta(days=i)
            if date == expected_date:
                consecutive_days += 1
            else:
                break

        return consecutive_days

    async def _calculate_conditional_progress(
        self,
        user_id: int,
        criteria: dict[str, Any],
        current_metrics: dict[str, Any]
    ) -> float:
        """計算條件型成就進度."""
        conditions = criteria.get("conditions", [])
        if not conditions:
            raise ValueError("條件型成就缺少 conditions")

        satisfied_conditions = 0
        len(conditions)

        for condition in conditions:
            condition_type = condition.get("type")
            if condition_type == "metric_threshold":
                metric_name = condition.get("metric")
                threshold = condition.get("threshold")
                if current_metrics.get(metric_name, 0) >= threshold:
                    satisfied_conditions += 1
            elif condition_type == "achievement_dependency":
                # 檢查是否已獲得指定成就
                required_achievement_id = condition.get("achievement_id")
                has_achievement = await self._repository.has_user_achievement(
                    user_id, required_achievement_id
                )
                if has_achievement:
                    satisfied_conditions += 1

        # 返回滿足條件的比例作為進度
        return float(satisfied_conditions)

    # =============================================================================
    # 進度驗證和邊界檢查
    # =============================================================================

    async def validate_progress_update(
        self,
        user_id: int,
        achievement_id: int,
        new_value: float
    ) -> tuple[bool, str | None]:
        """驗證進度更新的有效性.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            new_value: 新的進度值

        Returns:
            (是否有效, 錯誤訊息)
        """
        try:
            # 檢查成就是否存在
            achievement = await self._repository.get_achievement_by_id(achievement_id)
            if not achievement:
                return False, f"成就 {achievement_id} 不存在"

            # 檢查成就是否啟用
            if not achievement.is_active:
                return False, f"成就 {achievement_id} 未啟用"

            # 檢查進度值是否為非負數
            if new_value < 0:
                return False, "進度值不能為負數"

            # 檢查是否已經完成成就
            has_achievement = await self._repository.has_user_achievement(
                user_id, achievement_id
            )
            if has_achievement:
                return False, "用戶已獲得此成就"

            return True, None

        except Exception as e:
            logger.error(
                "進度更新驗證失敗",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "new_value": new_value,
                    "error": str(e)
                },
                exc_info=True
            )
            return False, f"驗證過程發生錯誤: {e!s}"

    # =============================================================================
    # 進度查詢和分析
    # =============================================================================

    async def get_user_progress_summary(self, user_id: int) -> dict[str, Any]:
        """取得用戶進度摘要.

        Args:
            user_id: 用戶 ID

        Returns:
            包含進度摘要的字典
        """
        try:
            # 取得所有進度記錄
            progresses = await self._repository.get_user_progresses(user_id)

            # 統計資料
            total_progresses = len(progresses)
            completed_count = sum(1 for p in progresses if p.is_completed)
            in_progress_count = total_progresses - completed_count

            # 計算平均進度
            if progresses:
                avg_progress = sum(p.progress_percentage for p in progresses) / total_progresses
            else:
                avg_progress = 0.0

            # 找出最接近完成的成就
            incomplete_progresses = [p for p in progresses if not p.is_completed]
            if incomplete_progresses:
                closest_to_completion = max(
                    incomplete_progresses,
                    key=lambda p: p.progress_percentage
                )
            else:
                closest_to_completion = None

            summary = {
                "total_progresses": total_progresses,
                "completed_count": completed_count,
                "in_progress_count": in_progress_count,
                "average_progress": round(avg_progress, 2),
                "closest_to_completion": {
                    "achievement_id": closest_to_completion.achievement_id,
                    "progress_percentage": closest_to_completion.progress_percentage
                } if closest_to_completion else None
            }

            logger.debug(
                "取得用戶進度摘要",
                extra={
                    "user_id": user_id,
                    **summary
                }
            )

            return summary

        except Exception as e:
            logger.error(
                "取得用戶進度摘要失敗",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    async def find_users_near_completion(
        self,
        achievement_id: int,
        threshold_percentage: float = 80.0
    ) -> list[tuple[int, float]]:
        """找出接近完成特定成就的用戶.

        Args:
            achievement_id: 成就 ID
            threshold_percentage: 進度閾值百分比

        Returns:
            (用戶ID, 進度百分比) 的元組列表
        """
        try:
            # 使用新添加的 repository 方法查詢接近完成的用戶
            users_near_completion = await self.repository.get_users_near_achievement_completion(
                achievement_id=achievement_id,
                threshold_percentage=threshold_percentage
            )

            logger.debug(
                f"找到 {len(users_near_completion)} 個用戶接近完成成就",
                extra={
                    "achievement_id": achievement_id,
                    "threshold_percentage": threshold_percentage,
                    "user_count": len(users_near_completion)
                }
            )

            return users_near_completion

        except Exception as e:
            logger.error(
                "查找接近完成成就的用戶失敗",
                extra={
                    "achievement_id": achievement_id,
                    "threshold_percentage": threshold_percentage,
                    "error": str(e)
                },
                exc_info=True
            )
            raise


__all__ = [
    "ProgressTracker",
]
