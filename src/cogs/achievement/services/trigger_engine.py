"""成就觸發檢查引擎.

此模組實作成就觸發檢查系統,提供:
- 成就條件檢查邏輯
- 自動觸發機制
- 條件評估引擎
- 觸發事件處理
- 成就解鎖邏輯

觸發引擎遵循以下設計原則:
- 支援多種成就類型的條件檢查
- 提供靈活的條件評估框架
- 整合進度追蹤和自動成就頒發
- 支援複雜條件組合和依賴關係
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..database.models import (
    Achievement,
    AchievementType,
    UserAchievement,
)

if TYPE_CHECKING:
    from ..database.repository import AchievementRepository
    from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


class TriggerEngine:
    """成就觸發檢查引擎.

    提供成就觸發檢查和自動頒發的核心功能,包含:
    - 條件檢查和評估邏輯
    - 自動成就觸發機制
    - 複雜條件組合處理
    - 觸發事件管理
    """

    def __init__(
        self, repository: AchievementRepository, progress_tracker: ProgressTracker
    ):
        """初始化觸發引擎.

        Args:
            repository: 成就資料存取庫
            progress_tracker: 進度追蹤器
        """
        self._repository = repository
        self._progress_tracker = progress_tracker

        logger.info("TriggerEngine 初始化完成")

    async def __aenter__(self) -> TriggerEngine:
        """異步上下文管理器進入."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        pass

    # =============================================================================
    # 成就條件檢查核心邏輯
    # =============================================================================

    async def check_achievement_trigger(
        self, user_id: int, achievement_id: int, trigger_context: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """檢查特定成就是否應該被觸發.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            trigger_context: 觸發上下文資料

        Returns:
            (是否應該觸發, 觸發原因描述)

        Raises:
            ValueError: 成就不存在或參數無效
        """
        try:
            # 檢查用戶是否已獲得此成就
            has_achievement = await self._repository.has_user_achievement(
                user_id, achievement_id
            )
            if has_achievement:
                return False, "用戶已獲得此成就"

            # 取得成就資料
            achievement = await self._repository.get_achievement_by_id(achievement_id)
            if not achievement:
                raise ValueError(f"成就 {achievement_id} 不存在")

            if not achievement.is_active:
                return False, "成就未啟用"

            # 根據成就類型檢查觸發條件
            should_trigger, reason = await self._check_type_specific_trigger(
                user_id=user_id,
                achievement=achievement,
                trigger_context=trigger_context,
            )

            if should_trigger:
                logger.info(
                    "成就觸發條件滿足",
                    extra={
                        "user_id": user_id,
                        "achievement_id": achievement_id,
                        "achievement_name": achievement.name,
                        "trigger_reason": reason,
                    },
                )

            return should_trigger, reason

        except Exception as e:
            logger.error(
                "成就觸發檢查失敗",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def _check_type_specific_trigger(
        self, user_id: int, achievement: Achievement, trigger_context: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """根據成就類型檢查特定的觸發條件.

        Args:
            user_id: 用戶 ID
            achievement: 成就物件
            trigger_context: 觸發上下文

        Returns:
            (是否應該觸發, 觸發原因)
        """
        achievement_type = achievement.type
        criteria = achievement.criteria

        if achievement_type == AchievementType.COUNTER:
            return await self._check_counter_trigger(
                user_id, achievement, criteria, trigger_context
            )
        elif achievement_type == AchievementType.MILESTONE:
            return await self._check_milestone_trigger(
                user_id, achievement, criteria, trigger_context
            )
        elif achievement_type == AchievementType.TIME_BASED:
            return await self._check_time_based_trigger(
                user_id, achievement, criteria, trigger_context
            )
        elif achievement_type == AchievementType.CONDITIONAL:
            return await self._check_conditional_trigger(
                user_id, achievement, criteria, trigger_context
            )
        else:
            return False, f"不支援的成就類型: {achievement_type}"

    async def _check_counter_trigger(
        self,
        user_id: int,
        achievement: Achievement,
        criteria: dict[str, Any],
        trigger_context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """檢查計數型成就觸發條件.

        支援複雜計數條件包含:
        - 基本目標值檢查
        - 時間窗口限制
        - 累積和增量模式
        - 多重計數器條件
        """
        target_value = criteria.get("target_value", 0)
        counter_field = criteria.get("counter_field")
        time_window = criteria.get("time_window")
        increment_mode = criteria.get(
            "increment_mode", "cumulative"
        )  # cumulative 或 incremental

        if not counter_field:
            return False, "計數型成就缺少 counter_field"

        # 取得當前進度
        progress = await self._repository.get_user_progress(user_id, achievement.id)
        current_value = progress.current_value if progress else 0.0

        # 處理時間窗口限制
        if time_window:
            # 檢查時間窗口內的計數
            windowed_value = await self._get_windowed_counter_value(
                user_id, achievement.id, counter_field, time_window, trigger_context
            )

            if increment_mode == "incremental":
                event_increment = trigger_context.get(counter_field, 0)
                if windowed_value + event_increment >= target_value:
                    return (
                        True,
                        f"時間窗口內計數達到目標值 {target_value} (窗口: {time_window})",
                    )
            elif windowed_value >= target_value:
                return (
                    True,
                    f"時間窗口內計數達到目標值 {target_value} (窗口: {time_window})",
                )

            return (
                False,
                f"時間窗口內計數尚未達到目標值 ({windowed_value}/{target_value}, 窗口: {time_window})",
            )

        # 處理複合條件
        if "conditions" in criteria:
            return await self._check_compound_counter_conditions(
                user_id, achievement, criteria["conditions"], trigger_context
            )

        if increment_mode == "incremental":
            event_increment = trigger_context.get(counter_field, 0)
            if current_value + event_increment >= target_value:
                return (
                    True,
                    f"計數達到目標值 {target_value} (當前: {current_value}, 增量: {event_increment})",
                )
        elif current_value >= target_value:
            return True, f"計數達到目標值 {target_value}"

        return False, f"計數尚未達到目標值 ({current_value}/{target_value})"

    async def _check_milestone_trigger(
        self,
        user_id: int,
        achievement: Achievement,
        criteria: dict[str, Any],
        trigger_context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """檢查里程碑型成就觸發條件.

        支援多階段里程碑檢查:
        - 基本里程碑達成
        - 多條件組合里程碑
        - 依賴關係檢查
        - 特定事件觸發里程碑
        """
        milestone_type = criteria.get("milestone_type")
        if not milestone_type:
            return False, "里程碑型成就缺少 milestone_type"

        # 處理多階段里程碑
        if milestone_type == "multi_stage":
            return await self._check_multi_stage_milestone(
                user_id, achievement, criteria, trigger_context
            )

        # 處理事件觸發里程碑
        if milestone_type == "event_triggered":
            return await self._check_event_triggered_milestone(
                user_id, achievement, criteria, trigger_context
            )

        # 處理條件組合里程碑
        if "required_conditions" in criteria:
            return await self._check_conditional_milestone(
                user_id, achievement, criteria, trigger_context
            )

        # 基本里程碑檢查
        target_value = criteria.get("target_value", 0)
        current_value = trigger_context.get(milestone_type, 0)

        # 支援不同的比較方式
        operator = criteria.get("operator", ">=")
        condition_met = self._evaluate_numeric_condition(
            current_value, operator, target_value
        )

        if condition_met:
            return (
                True,
                f"里程碑達到 {milestone_type}: {current_value} {operator} {target_value}",
            )
        else:
            return (
                False,
                f"里程碑未達到 {milestone_type}: {current_value} 不滿足 {operator} {target_value}",
            )

    async def _check_time_based_trigger(
        self,
        user_id: int,
        achievement: Achievement,
        criteria: dict[str, Any],
        _trigger_context: dict[str, Any],  # 重命名未使用參數
    ) -> tuple[bool, str | None]:
        """檢查時間型成就觸發條件."""
        target_value = criteria.get("target_value", 0)
        time_unit = criteria.get("time_unit", "days")

        # 取得當前進度
        progress = await self._repository.get_user_progress(user_id, achievement.id)
        if not progress or not progress.progress_data:
            return False, "沒有時間型進度資料"

        streak_dates = progress.progress_data.get("streak_dates", [])

        if time_unit == "days":
            consecutive_days = self._calculate_consecutive_days(streak_dates)
            if consecutive_days >= target_value:
                return True, f"連續 {consecutive_days} 天達到目標"
            return False, f"連續天數不足 ({consecutive_days}/{target_value})"

        return False, f"不支援的時間單位: {time_unit}"

    def _calculate_consecutive_days(self, streak_dates: list[str]) -> int:
        """計算連續天數(與 ProgressTracker 中的邏輯一致)."""
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

    async def _check_conditional_trigger(
        self,
        user_id: int,
        _achievement: Achievement,  # 重命名未使用參數
        criteria: dict[str, Any],
        trigger_context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """檢查條件型成就觸發條件."""
        conditions = criteria.get("conditions", [])
        require_all = criteria.get("require_all", True)  # 預設需要滿足所有條件

        if not conditions:
            return False, "條件型成就缺少 conditions"

        satisfied_conditions = []
        failed_conditions = []

        for condition in conditions:
            is_satisfied, reason = await self._evaluate_single_condition(
                user_id, condition, trigger_context
            )

            if is_satisfied:
                satisfied_conditions.append(reason)
            else:
                failed_conditions.append(reason)

        if require_all:
            # 需要滿足所有條件
            if len(satisfied_conditions) == len(conditions):
                return True, f"滿足所有條件: {', '.join(satisfied_conditions)}"
            else:
                return False, f"未滿足條件: {', '.join(failed_conditions)}"
        # 只需要滿足任一條件
        elif satisfied_conditions:
            return True, f"滿足條件: {satisfied_conditions[0]}"
        else:
            return False, f"未滿足任何條件: {', '.join(failed_conditions)}"

    async def _evaluate_single_condition(
        self, user_id: int, condition: dict[str, Any], trigger_context: dict[str, Any]
    ) -> tuple[bool, str]:
        """評估單一條件.

        Args:
            user_id: 用戶 ID
            condition: 條件定義
            trigger_context: 觸發上下文

        Returns:
            (是否滿足, 條件描述)
        """
        condition_type = condition.get("type")

        if condition_type == "metric_threshold":
            return self._evaluate_metric_threshold_condition(condition, trigger_context)
        elif condition_type == "achievement_dependency":
            return await self._evaluate_achievement_dependency_condition(
                user_id, condition
            )
        elif condition_type == "time_range":
            return self._evaluate_time_range_condition(condition)
        else:
            return False, f"不支援的條件類型: {condition_type}"

    def _evaluate_metric_threshold_condition(
        self, condition: dict[str, Any], trigger_context: dict[str, Any]
    ) -> tuple[bool, str]:
        """評估指標閾值條件."""
        metric_name = condition.get("metric")
        threshold = condition.get("threshold", 0)
        operator = condition.get("operator", ">=")

        metric_value = trigger_context.get(metric_name, 0)

        if operator == ">=":
            satisfied = metric_value >= threshold
        elif operator == ">":
            satisfied = metric_value > threshold
        elif operator == "<=":
            satisfied = metric_value <= threshold
        elif operator == "<":
            satisfied = metric_value < threshold
        elif operator == "==":
            satisfied = metric_value == threshold
        else:
            return False, f"不支援的比較運算子: {operator}"

        if satisfied:
            return True, f"{metric_name} {operator} {threshold} (實際: {metric_value})"
        else:
            return (
                False,
                f"{metric_name} 不滿足 {operator} {threshold} (實際: {metric_value})",
            )

    async def _evaluate_achievement_dependency_condition(
        self, user_id: int, condition: dict[str, Any]
    ) -> tuple[bool, str]:
        """評估成就依賴條件."""
        required_achievement_id = condition.get("achievement_id")
        if not required_achievement_id:
            return False, "成就依賴條件缺少 achievement_id"

        has_achievement = await self._repository.has_user_achievement(
            user_id, required_achievement_id
        )

        if has_achievement:
            return True, f"已獲得依賴成就 {required_achievement_id}"
        else:
            return False, f"尚未獲得依賴成就 {required_achievement_id}"

    def _evaluate_time_range_condition(
        self, condition: dict[str, Any]
    ) -> tuple[bool, str]:
        """評估時間範圍條件."""
        start_time = condition.get("start_time")
        end_time = condition.get("end_time")
        current_time = datetime.now()

        if start_time and end_time:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)

            if start <= current_time <= end:
                return True, f"在時間範圍內 ({start_time} - {end_time})"
            else:
                return False, f"不在時間範圍內 ({start_time} - {end_time})"
        else:
            return False, "時間範圍條件缺少 start_time 或 end_time"

    # =============================================================================
    # 自動觸發機制
    # =============================================================================

    async def process_automatic_triggers(
        self, user_id: int, trigger_event: str, event_data: dict[str, Any]
    ) -> list[UserAchievement]:
        """處理自動觸發檢查並頒發符合條件的成就.

        Args:
            user_id: 用戶 ID
            trigger_event: 觸發事件類型
            event_data: 事件資料

        Returns:
            新獲得的成就列表
        """
        try:
            # 取得所有啟用的成就
            active_achievements = await self._repository.list_achievements(
                active_only=True
            )

            # 過濾出與此事件相關的成就
            relevant_achievements = self._filter_achievements_by_event(
                active_achievements, trigger_event
            )

            newly_earned_achievements = []

            for achievement in relevant_achievements:
                try:
                    # 檢查是否應該觸發
                    should_trigger, reason = await self.check_achievement_trigger(
                        user_id=user_id,
                        achievement_id=achievement.id,
                        trigger_context=event_data,
                    )

                    if should_trigger:
                        # 頒發成就
                        user_achievement = await self._repository.award_achievement(
                            user_id, achievement.id
                        )
                        newly_earned_achievements.append(user_achievement)

                        logger.info(
                            "自動頒發成就成功",
                            extra={
                                "user_id": user_id,
                                "achievement_id": achievement.id,
                                "achievement_name": achievement.name,
                                "trigger_event": trigger_event,
                                "trigger_reason": reason,
                            },
                        )

                except Exception as e:
                    logger.error(
                        "自動觸發成就處理失敗",
                        extra={
                            "user_id": user_id,
                            "achievement_id": achievement.id,
                            "trigger_event": trigger_event,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    continue

            logger.info(
                "自動觸發處理完成",
                extra={
                    "user_id": user_id,
                    "trigger_event": trigger_event,
                    "checked_achievements": len(relevant_achievements),
                    "newly_earned": len(newly_earned_achievements),
                },
            )

            return newly_earned_achievements

        except Exception as e:
            logger.error(
                "自動觸發處理失敗",
                extra={
                    "user_id": user_id,
                    "trigger_event": trigger_event,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    def _filter_achievements_by_event(
        self, achievements: list[Achievement], trigger_event: str
    ) -> list[Achievement]:
        """根據觸發事件過濾相關的成就.

        Args:
            achievements: 成就列表
            trigger_event: 觸發事件類型

        Returns:
            相關的成就列表
        """
        # 定義事件與成就類型的對應關係
        event_type_mapping = {
            "message_sent": [AchievementType.COUNTER],
            "user_join": [AchievementType.MILESTONE],
            "daily_login": [AchievementType.TIME_BASED],
            "achievement_earned": [AchievementType.CONDITIONAL],
            "level_up": [AchievementType.MILESTONE, AchievementType.CONDITIONAL],
            "interaction": [AchievementType.COUNTER, AchievementType.CONDITIONAL],
        }

        relevant_types = event_type_mapping.get(trigger_event, [])
        if not relevant_types:
            # 如果沒有定義對應關係,返回所有成就
            return achievements

        return [
            achievement
            for achievement in achievements
            if achievement.type in relevant_types
        ]

    # =============================================================================
    # 批量觸發檢查
    # =============================================================================

    async def batch_check_triggers_for_users(
        self, user_ids: list[int], trigger_event: str, event_data: dict[str, Any]
    ) -> dict[int, list[UserAchievement]]:
        """批量檢查多個用戶的成就觸發.

        Args:
            user_ids: 用戶 ID 列表
            trigger_event: 觸發事件類型
            event_data: 事件資料

        Returns:
            用戶 ID 到新獲得成就列表的映射
        """
        results = {}
        errors = []

        for user_id in user_ids:
            try:
                newly_earned = await self.process_automatic_triggers(
                    user_id=user_id, trigger_event=trigger_event, event_data=event_data
                )
                results[user_id] = newly_earned
            except Exception as e:
                errors.append(f"用戶 {user_id} 觸發檢查失敗: {e!s}")
                results[user_id] = []

        if errors:
            logger.warning(
                "批量觸發檢查部分失敗",
                extra={
                    "total_users": len(user_ids),
                    "success_users": len([r for r in results.values() if r]),
                    "errors": errors,
                },
            )

        logger.info(
            "批量觸發檢查完成",
            extra={
                "total_users": len(user_ids),
                "processed_users": len(results),
                "failed_users": len(errors),
            },
        )

        return results

    # =============================================================================
    # 觸發事件處理
    # =============================================================================

    async def handle_trigger_event(
        self, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """處理觸發事件.

        Args:
            event_type: 事件類型
            event_data: 事件資料
        """
        try:
            user_id = event_data.get("user_id")
            if not user_id:
                logger.warning(
                    "觸發事件缺少 user_id",
                    extra={"event_type": event_type, "event_data": event_data},
                )
                return

            # 更新相關的進度
            await self._update_progress_from_event(user_id, event_type, event_data)

            # 檢查自動觸發
            newly_earned = await self.process_automatic_triggers(
                user_id=user_id, trigger_event=event_type, event_data=event_data
            )

            if newly_earned:
                logger.info(
                    "事件觸發獲得新成就",
                    extra={
                        "user_id": user_id,
                        "event_type": event_type,
                        "newly_earned_count": len(newly_earned),
                        "achievement_ids": [ua.achievement_id for ua in newly_earned],
                    },
                )

        except Exception as e:
            logger.error(
                "處理觸發事件失敗",
                extra={
                    "event_type": event_type,
                    "event_data": event_data,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def _update_progress_from_event(
        self, user_id: int, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """根據事件更新相關的成就進度.

        Args:
            user_id: 用戶 ID
            event_type: 事件類型
            event_data: 事件資料
        """
        # 取得所有啟用的成就
        active_achievements = await self._repository.list_achievements(active_only=True)

        # 過濾出與此事件相關的成就
        relevant_achievements = self._filter_achievements_by_event(
            active_achievements, event_type
        )

        for achievement in relevant_achievements:
            try:
                # 根據成就類型更新進度
                await self._update_achievement_progress_from_event(
                    user_id=user_id,
                    achievement=achievement,
                    event_type=event_type,
                    event_data=event_data,
                )
            except Exception as e:
                logger.error(
                    "從事件更新成就進度失敗",
                    extra={
                        "user_id": user_id,
                        "achievement_id": achievement.id,
                        "event_type": event_type,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                continue

    async def _update_achievement_progress_from_event(
        self,
        user_id: int,
        achievement: Achievement,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """根據事件更新特定成就的進度.

        Args:
            user_id: 用戶 ID
            achievement: 成就物件
            event_type: 事件類型
            event_data: 事件資料
        """
        # 檢查是否已獲得成就
        has_achievement = await self._repository.has_user_achievement(
            user_id, achievement.id
        )
        if has_achievement:
            return

        # 根據成就類型和事件類型計算進度增量
        increment_value = self._calculate_progress_increment(
            achievement, event_type, event_data
        )

        if increment_value > 0:
            await self._progress_tracker.update_user_progress(
                user_id=user_id,
                achievement_id=achievement.id,
                increment_value=increment_value,
                progress_data={
                    "last_event": event_type,
                    "event_timestamp": datetime.now().isoformat(),
                },
            )

    def _calculate_progress_increment(
        self, achievement: Achievement, event_type: str, event_data: dict[str, Any]
    ) -> float:
        """計算事件對成就進度的增量.

        Args:
            achievement: 成就物件
            event_type: 事件類型
            event_data: 事件資料

        Returns:
            進度增量值
        """
        # 簡單的事件到進度增量的映射
        # 實際應用中可能需要更複雜的邏輯

        if achievement.type == AchievementType.COUNTER:
            # 計數型成就通常每個事件增加 1
            return 1.0
        elif achievement.type == AchievementType.TIME_BASED:
            # 時間型成就根據時間單位增加
            if event_type == "daily_login":
                return 1.0  # 每日登入增加 1 天
        elif achievement.type == AchievementType.MILESTONE:
            # 里程碑型成就根據事件資料中的值增加
            milestone_type = achievement.criteria.get("milestone_type")
            if milestone_type and milestone_type in event_data:
                return float(event_data[milestone_type])

        return 0.0

    # =============================================================================
    # 複雜計數條件輔助方法
    # =============================================================================

    async def _get_windowed_counter_value(
        self,
        user_id: int,
        achievement_id: int,
        counter_field: str,
        time_window: str,
        _trigger_context: dict[str, Any],
    ) -> float:
        """取得時間窗口內的計數值.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            counter_field: 計數字段
            time_window: 時間窗口(如 "7d", "30d", "1h")
            _trigger_context: 觸發上下文(未使用)

        Returns:
            時間窗口內的計數值
        """
        try:
            # 解析時間窗口
            window_seconds = self._parse_time_window(time_window)
            if window_seconds <= 0:
                return 0.0

            # 從進度資料中取得時間窗口內的計數
            progress = await self._repository.get_user_progress(user_id, achievement_id)
            if not progress or not progress.progress_data:
                return 0.0

            # 取得窗口內的事件資料
            windowed_events = progress.progress_data.get("windowed_events", [])
            current_time = datetime.now()

            # 過濾時間窗口內的事件
            windowed_value = 0.0
            for event in windowed_events:
                event_time = datetime.fromisoformat(event.get("timestamp", ""))
                if (current_time - event_time).total_seconds() <= window_seconds:
                    windowed_value += event.get(counter_field, 0)

            return windowed_value

        except Exception as e:
            logger.error(
                "取得時間窗口計數值失敗",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "counter_field": counter_field,
                    "time_window": time_window,
                    "error": str(e),
                },
            )
            return 0.0

    async def _check_compound_counter_conditions(
        self,
        user_id: int,
        achievement: Achievement,
        conditions: list[dict[str, Any]],
        trigger_context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """檢查複合計數條件.

        Args:
            user_id: 用戶 ID
            achievement: 成就物件
            conditions: 條件列表
            trigger_context: 觸發上下文

        Returns:
            (是否滿足, 條件描述)
        """
        satisfied_conditions = []
        failed_conditions = []

        for condition in conditions:
            counter_field = condition.get("field")
            target_value = condition.get("target_value", 0)
            operator = condition.get("operator", ">=")

            if not counter_field:
                failed_conditions.append("缺少計數字段")
                continue

            # 取得當前計數值
            if "time_window" in condition:
                current_value = await self._get_windowed_counter_value(
                    user_id,
                    achievement.id,
                    counter_field,
                    condition["time_window"],
                    trigger_context,
                )
            else:
                progress = await self._repository.get_user_progress(
                    user_id, achievement.id
                )
                current_value = progress.current_value if progress else 0.0

            # 評估條件
            condition_met = self._evaluate_numeric_condition(
                current_value, operator, target_value
            )

            condition_desc = (
                f"{counter_field} {operator} {target_value} (實際: {current_value})"
            )

            if condition_met:
                satisfied_conditions.append(condition_desc)
            else:
                failed_conditions.append(condition_desc)

        # 檢查邏輯運算子
        logic_operator = achievement.criteria.get("logic_operator", "AND")

        if logic_operator == "AND":
            if len(satisfied_conditions) == len(conditions):
                return True, f"滿足所有複合條件: {', '.join(satisfied_conditions)}"
            else:
                return False, f"未滿足複合條件: {', '.join(failed_conditions)}"
        elif satisfied_conditions:
            return True, f"滿足複合條件: {satisfied_conditions[0]}"
        else:
            return False, f"未滿足任何複合條件: {', '.join(failed_conditions)}"

    def _parse_time_window(self, time_window: str) -> int:
        """解析時間窗口字符串為秒數.

        Args:
            time_window: 時間窗口字符串(如 "7d", "24h", "30m")

        Returns:
            秒數
        """
        try:
            if not time_window:
                return 0

            # 解析數值和單位
            unit = time_window[-1].lower()
            value = int(time_window[:-1])

            unit_multipliers = {
                "s": 1,  # 秒
                "m": 60,  # 分鐘
                "h": 3600,  # 小時
                "d": 86400,  # 天
                "w": 604800,  # 週
            }

            multiplier = unit_multipliers.get(unit, 0)
            return value * multiplier

        except (ValueError, IndexError):
            logger.warning(f"無法解析時間窗口: {time_window}")
            return 0

    def _evaluate_numeric_condition(
        self, current_value: float, operator: str, target_value: float
    ) -> bool:
        """評估數值條件.

        Args:
            current_value: 當前值
            operator: 比較運算子
            target_value: 目標值

        Returns:
            是否滿足條件
        """
        operators = {
            ">=": lambda x, y: x >= y,
            ">": lambda x, y: x > y,
            "<=": lambda x, y: x <= y,
            "<": lambda x, y: x < y,
            "==": lambda x, y: x == y,
            "!=": lambda x, y: x != y,
        }

        operation = operators.get(operator)
        if not operation:
            logger.warning(f"不支援的運算子: {operator}")
            return False

        return operation(current_value, target_value)

    # =============================================================================
    # 里程碑型成就輔助方法
    # =============================================================================

    async def _check_multi_stage_milestone(
        self,
        user_id: int,
        achievement: Achievement,
        criteria: dict[str, Any],
        trigger_context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """檢查多階段里程碑成就.

        支援階段性里程碑,每個階段有不同的要求.
        """
        stages = criteria.get("stages", [])
        if not stages:
            return False, "多階段里程碑缺少 stages 定義"

        # 取得當前進度
        progress = await self._repository.get_user_progress(user_id, achievement.id)
        current_stage = 0

        if progress and progress.progress_data:
            current_stage = progress.progress_data.get("current_stage", 0)

        # 檢查是否已完成所有階段
        if current_stage >= len(stages):
            return True, f"所有 {len(stages)} 個階段已完成"

        # 檢查當前階段是否滿足條件
        stage = stages[current_stage]
        stage_condition = stage.get("condition", {})

        # 評估階段條件
        condition_met = await self._evaluate_stage_condition(
            user_id, stage_condition, trigger_context
        )

        if condition_met:
            # 記錄階段完成並檢查是否為最後階段
            new_stage = current_stage + 1
            if new_stage >= len(stages):
                return True, f"完成最終階段 {current_stage + 1}/{len(stages)}"
            else:
                # 更新階段進度但不觸發成就
                await self._update_stage_progress(user_id, achievement.id, new_stage)
                return (
                    False,
                    f"完成階段 {current_stage + 1}/{len(stages)},進入下一階段",
                )

        return False, f"階段 {current_stage + 1}/{len(stages)} 尚未完成"

    async def _check_event_triggered_milestone(
        self,
        user_id: int,
        achievement: Achievement,
        criteria: dict[str, Any],
        trigger_context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """檢查事件觸發里程碑成就.

        基於特定事件序列或組合觸發的里程碑.
        """
        required_events = criteria.get("required_events", [])
        event_sequence = criteria.get("event_sequence", False)  # 是否需要按順序發生

        if not required_events:
            return False, "事件觸發里程碑缺少 required_events"

        # 取得事件歷史
        progress = await self._repository.get_user_progress(user_id, achievement.id)
        event_history = []

        if progress and progress.progress_data:
            event_history = progress.progress_data.get("event_history", [])

        # 添加當前事件到歷史
        current_event = {
            "event_type": trigger_context.get("event_type"),
            "timestamp": datetime.now().isoformat(),
            "data": trigger_context,
        }

        if event_sequence:
            # 檢查事件序列
            return self._check_event_sequence(
                required_events, [*event_history, current_event]
            )
        else:
            return self._check_event_combination(
                required_events, [*event_history, current_event]
            )

    async def _check_conditional_milestone(
        self,
        user_id: int,
        _achievement: Achievement,
        criteria: dict[str, Any],
        trigger_context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """檢查條件組合里程碑成就.

        基於多個條件組合的複雜里程碑.
        """
        required_conditions = criteria.get("required_conditions", {})
        condition_logic = criteria.get("condition_logic", "AND")

        satisfied_conditions = []
        failed_conditions = []

        for condition_name, condition_def in required_conditions.items():
            is_satisfied = await self._evaluate_milestone_condition(
                user_id, condition_name, condition_def, trigger_context
            )

            if is_satisfied:
                satisfied_conditions.append(condition_name)
            else:
                failed_conditions.append(condition_name)

        # 根據邏輯運算子評估結果
        if condition_logic == "AND":
            all_satisfied = len(satisfied_conditions) == len(required_conditions)
            if all_satisfied:
                return True, f"滿足所有里程碑條件: {', '.join(satisfied_conditions)}"
            else:
                return False, f"未滿足里程碑條件: {', '.join(failed_conditions)}"
        elif satisfied_conditions:
            return True, f"滿足里程碑條件: {satisfied_conditions[0]}"
        else:
            return False, f"未滿足任何里程碑條件: {', '.join(failed_conditions)}"

    async def _evaluate_stage_condition(
        self, user_id: int, condition: dict[str, Any], trigger_context: dict[str, Any]
    ) -> bool:
        """評估階段條件.

        Args:
            user_id: 用戶 ID
            condition: 階段條件定義
            trigger_context: 觸發上下文

        Returns:
            是否滿足階段條件
        """
        condition_type = condition.get("type")

        if condition_type == "metric":
            metric_name = condition.get("metric")
            threshold = condition.get("threshold", 0)
            operator = condition.get("operator", ">=")

            current_value = trigger_context.get(metric_name, 0)
            return self._evaluate_numeric_condition(current_value, operator, threshold)

        elif condition_type == "event":
            expected_event = condition.get("event_type")
            return trigger_context.get("event_type") == expected_event

        elif condition_type == "achievement":
            required_achievement_id = condition.get("achievement_id")
            return await self._repository.has_user_achievement(
                user_id, required_achievement_id
            )

        return False

    async def _update_stage_progress(
        self, user_id: int, achievement_id: int, new_stage: int
    ) -> None:
        """更新階段進度.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            new_stage: 新的階段編號
        """
        progress_data = {
            "current_stage": new_stage,
            "stage_updated_at": datetime.now().isoformat(),
        }

        await self._progress_tracker.update_user_progress(
            user_id=user_id,
            achievement_id=achievement_id,
            increment_value=0,  # 階段更新不改變數值
            progress_data=progress_data,
        )

    def _check_event_sequence(
        self, required_events: list[str], event_history: list[dict[str, Any]]
    ) -> tuple[bool, str | None]:
        """檢查事件序列.

        檢查事件是否按照要求的順序發生.
        """
        if len(event_history) < len(required_events):
            return (
                False,
                f"事件序列不完整 ({len(event_history)}/{len(required_events)})",
            )

        # 檢查最近的事件是否符合序列
        recent_events = event_history[-len(required_events) :]

        for i, (expected_event, actual_event) in enumerate(
            zip(required_events, recent_events, strict=False)
        ):
            if actual_event.get("event_type") != expected_event:
                return (
                    False,
                    f"事件序列不匹配,位置 {i + 1}: 期望 {expected_event}, 實際 {actual_event.get('event_type')}",
                )

        return True, f"事件序列完成: {', '.join(required_events)}"

    def _check_event_combination(
        self, required_events: list[str], event_history: list[dict[str, Any]]
    ) -> tuple[bool, str | None]:
        """檢查事件組合.

        檢查是否發生了所有要求的事件(不考慮順序).
        """
        occurred_events = {event.get("event_type") for event in event_history}
        missing_events = set(required_events) - occurred_events

        if not missing_events:
            return True, f"所有要求事件已發生: {', '.join(required_events)}"
        else:
            return False, f"缺少事件: {', '.join(missing_events)}"

    async def _evaluate_milestone_condition(
        self,
        user_id: int,
        condition_name: str,
        condition_def: dict[str, Any],
        trigger_context: dict[str, Any],
    ) -> bool:
        """評估里程碑條件.

        Args:
            user_id: 用戶 ID
            condition_name: 條件名稱
            condition_def: 條件定義
            trigger_context: 觸發上下文

        Returns:
            是否滿足條件
        """
        condition_type = condition_def.get("type")

        if condition_type == "user_stat":
            stat_name = condition_def.get("stat")
            threshold = condition_def.get("threshold", 0)
            operator = condition_def.get("operator", ">=")

            # 從觸發上下文取得用戶統計
            current_value = trigger_context.get(stat_name, 0)
            return self._evaluate_numeric_condition(current_value, operator, threshold)

        elif condition_type == "guild_role":
            role_id = condition_def.get("role_id")
            user_roles = trigger_context.get("user_roles", [])
            return role_id in user_roles

        elif condition_type == "time_constraint":
            start_time = condition_def.get("start_time")
            end_time = condition_def.get("end_time")
            current_time = datetime.now()

            if start_time and end_time:
                start = datetime.fromisoformat(start_time)
                end = datetime.fromisoformat(end_time)
                return start <= current_time <= end

        return False


__all__ = [
    "TriggerEngine",
]
