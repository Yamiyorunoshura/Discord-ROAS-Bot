"""
¯ ActivityModule - æ´»èºåº¦æ¨¡å¡çµ±ä¸API
- æä¾çµ±ä¸çæ´»èºåº¦APIæ¥å£
- æ´åååç¨å¼éè¼¯åè½
- å¯¦ç¾ç·©å­æ©å¶åé¯èª¤èç
- æ¯æ´æ¬éæª¢æ¥åæ§è½ç£æ§
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .cache import ActivityCache
from .calculator import ActivityCalculator
from .logic_apis import LogicAPIs
from .renderer import ActivityRenderer

logger = logging.getLogger("activity_module")


@dataclass
class ActivityData:
    """æ´»èºåº¦æ¸æçµæ§"""

    user_id: str
    activity_score: float
    last_activity: datetime | None = None
    total_messages: int = 0
    response_time: float = 0.0
    rank: int | None = None
    level: int | None = None


class ActivityAPIError(Exception):
    """Activity API é¯èª¤"""

    pass


class UserNotFoundError(ActivityAPIError):
    """ç¨æ¶ä¸å­å¨é¯èª¤"""

    pass


class ActivityModule:
    """
    æ´»èºåº¦æ¨¡å¡çµ±ä¸API
    - æ´åååç¨å¼éè¼¯åè½
    - æä¾çµ±ä¸çAPIæ¥å£
    - å¯¦ç¾ç·©å­åé¯èª¤èç
    """

    def __init__(self):
        """åå§åæ´»èºåº¦æ¨¡å¡"""
        self.logic_apis = LogicAPIs()
        self.cache = ActivityCache()
        self.calculator = ActivityCalculator()
        self.renderer = ActivityRenderer()

        # æ§è½ç£æ§
        self.api_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info("ActivityModule åå§åæå")

    def get_unified_activity_api(self, user_id: str) -> ActivityData:
        """
        ç²åçµ±ä¸æ´»èºåº¦APIæ¸æ

        Args:
            user_id: ç¨æ¶ID

        Returns:
            ActivityData: æ´»èºåº¦æ¸æ

        Raises:
            UserNotFoundError: ç¨æ¶ä¸å­å¨
            ActivityAPIError: APIé¯èª¤
        """
        try:
            start_time = time.time()
            self.api_calls += 1

            # æª¢æ¥ç·©å­
            cache_key = f"activity_{user_id}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                self.cache_hits += 1
                logger.debug(f"ç·©å­å½ä¸­: {user_id}")
                return cached_data

            self.cache_misses += 1
            logger.debug(f"ç·©å­æªå½ä¸­: {user_id}")

            # èª¿ç¨éè¼¯APIç²åç¨æ¶æ¸æ
            user_data = self.logic_apis.get_user_data(user_id)
            if not user_data:
                raise UserNotFoundError(f"ç¨æ¶ {user_id} ä¸å­å¨")

            # è¨ç®æ´»èºåº¦åæ¸
            activity_score = self.calculate_activity_score(user_data)

            # ç²åæååç­ç´
            rank = self.logic_apis.get_user_rank(user_id)
            level = self.calculator.calculate_level(activity_score)

            # æ§å»ºæ´»èºåº¦æ¸æ
            activity_data = ActivityData(
                user_id=user_id,
                activity_score=activity_score,
                last_activity=user_data.get("last_activity"),
                total_messages=user_data.get("total_messages", 0),
                response_time=user_data.get("response_time", 0.0),
                rank=rank,
                level=level,
            )

            # å­å¥ç·©å­ (5åéTTL)
            self.cache.set(cache_key, activity_data, ttl=300)

            response_time = time.time() - start_time
            logger.info(
                f"æ´»èºåº¦æ¸æç²åæå: {user_id}, åæ¸: {activity_score}, é¿ææé: {response_time:.3f}s"
            )

            return activity_data

        except UserNotFoundError:
            logger.warning(f"ç¨æ¶ä¸å­å¨: {user_id}")
            raise
        except Exception as e:
            logger.error(f"ç²åæ´»èºåº¦æ¸æå¤±æ: {user_id}, é¯èª¤: {e}")
            raise ActivityAPIError(f"ç²åæ´»èºåº¦æ¸æå¤±æ: {e!s}") from e

    def calculate_activity_score(self, user_data: dict[str, Any]) -> float:
        """
        è¨ç®æ´»èºåº¦åæ¸ (ä½¿ç¨ numpy åªåçµ±è¨è¨ç®)

        Args:
            user_data: ç¨æ¶æ¸æ

        Returns:
            float: æ´»èºåº¦åæ¸ (0-100)
        """
        try:
            # æ¶éææåæ¸çµä»¶
            score_components = []

            # åºç¤åæ¸
            base_score = user_data.get("base_score", 0)
            score_components.append(base_score)

            # è¨æ¯çåµ
            message_bonus = user_data.get("total_messages", 0) * 0.1
            score_components.append(message_bonus)

            # é¿ææéçåµ
            response_time = user_data.get("response_time", 0)
            response_bonus = max(0, 10 - response_time) * 0.5
            score_components.append(response_bonus)

            # æ´»èºåº¦çåµ
            activity_bonus = user_data.get("activity_bonus", 0)
            score_components.append(activity_bonus)

            # ä½¿ç¨ numpy åéåè¨ç®ç¸½å
            total_score = self.calculator.performance_service.optimize_calculations(
                score_components, "sum"
            )

            # ç¢ºä¿åæ¸å¨0-100ç¯åå§
            return max(0, min(100, total_score))

        except Exception as e:
            logger.error(f"è¨ç®æ´»èºåº¦åæ¸å¤±æ: {e}")
            return 0.0

    def get_user_activity_history(
        self, user_id: str, days: int = 30
    ) -> list[ActivityData]:
        """
        ç²åç¨æ¶æ´»èºåº¦æ­·å²

        Args:
            user_id: ç¨æ¶ID
            days: æ­·å²å¤©æ¸

        Returns:
            List[ActivityData]: æ´»èºåº¦æ­·å²æ¸æ
        """
        try:
            cache_key = f"history_{user_id}_{days}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data

            # å¾éè¼¯APIç²åæ­·å²æ¸æ
            history_data = self.logic_apis.get_user_activity_history(user_id, days)

            # è½æçºActivityDataæ ¼å¼
            activity_history = []
            for data in history_data:
                activity_data = ActivityData(
                    user_id=user_id,
                    activity_score=data.get("score", 0),
                    last_activity=data.get("timestamp"),
                    total_messages=data.get("messages", 0),
                )
                activity_history.append(activity_data)

            # å­å¥ç·©å­ (10åéTTL)
            self.cache.set(cache_key, activity_history, ttl=600)

            return activity_history

        except Exception as e:
            logger.error(f"ç²åæ´»èºåº¦æ­·å²å¤±æ: {user_id}, é¯èª¤: {e}")
            return []

    def get_leaderboard(self, guild_id: str, limit: int = 10) -> list[ActivityData]:
        """
        ç²åæè¡æ¦

        Args:
            guild_id: ä¼ºæå¨ID
            limit: æè¡æ¦æ¸ééå¶

        Returns:
            List[ActivityData]: æè¡æ¦æ¸æ
        """
        try:
            cache_key = f"leaderboard_{guild_id}_{limit}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data

            # å¾éè¼¯APIç²åæè¡æ¦æ¸æ
            leaderboard_data = self.logic_apis.get_leaderboard(guild_id, limit)

            # è½æçºActivityDataæ ¼å¼
            leaderboard = []
            for i, data in enumerate(leaderboard_data, 1):
                activity_data = ActivityData(
                    user_id=data.get("user_id"),
                    activity_score=data.get("score", 0),
                    total_messages=data.get("messages", 0),
                    rank=i,
                )
                leaderboard.append(activity_data)

            # å­å¥ç·©å­ (2åéTTL)
            self.cache.set(cache_key, leaderboard, ttl=120)

            return leaderboard

        except Exception as e:
            logger.error(f"ç²åæè¡æ¦å¤±æ: {guild_id}, é¯èª¤: {e}")
            return []

    def update_user_activity(
        self, user_id: str, guild_id: str, activity_type: str = "message"
    ) -> bool:
        """
        æ´æ°ç¨æ¶æ´»èºåº¦

        Args:
            user_id: ç¨æ¶ID
            guild_id: ä¼ºæå¨ID
            activity_type: æ´»èºåº¦é¡å

        Returns:
            bool: æ´æ°æ¯å¦æå
        """
        try:
            # èª¿ç¨éè¼¯APIæ´æ°æ´»èºåº¦
            success = self.logic_apis.update_user_activity(
                user_id, guild_id, activity_type
            )

            if success:
                # æ¸é¤ç¸éç·©å­
                self.cache.delete(f"activity_{user_id}")
                self.cache.delete(f"leaderboard_{guild_id}")
                logger.info(f"æ´»èºåº¦æ´æ°æå: {user_id}")

            return success

        except Exception as e:
            logger.error(f"æ´»èºåº¦æ´æ°å¤±æ: {user_id}, é¯èª¤: {e}")
            return False

    def get_performance_metrics(self) -> dict[str, Any]:
        """
        ç²åæ§è½ææ¨

        Returns:
            Dict[str, Any]: æ§è½ææ¨æ¸æ
        """
        total_calls = self.api_calls + self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_calls * 100) if total_calls > 0 else 0

        return {
            "api_calls": self.api_calls,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "average_response_time": self._calculate_average_response_time(),
        }

    def _calculate_average_response_time(self) -> float:
        """è¨ç®å¹³åé¿ææé"""
        # éè£¡å¯ä»¥å¯¦ç¾æ´è¤éçé¿ææéè¨ç®
        return 0.1  # ç°¡åå¯¦ç¾

    def clear_cache(self, pattern: str | None = None):
        """
        æ¸é¤ç·©å­

        Args:
            pattern: ç·©å­æ¨¡å¼å¹é
        """
        self.cache.clear(pattern)
        logger.info(f"ç·©å­å·²æ¸é¤: {pattern or 'all'}")

    def get_cache_stats(self) -> dict[str, Any]:
        """
        ç²åç·©å­çµ±è¨

        Returns:
            Dict[str, Any]: ç·©å­çµ±è¨æ¸æ
        """
        return self.cache.get_stats()

    def batch_calculate_activity_scores(
        self, users_data: list[dict[str, Any]]
    ) -> list[float]:
        """
        æ¹éè¨ç®å¤åç¨æ¶çæ´»èºåº¦åæ¸ (ä½¿ç¨ numpy åªå)

        Args:
            users_data: ç¨æ¶æ¸æåè¡¨

        Returns:
            List[float]: æ´»èºåº¦åæ¸åè¡¨
        """
        if not users_data:
            return []

        try:
            # æåææåæ¸çµä»¶
            base_scores = [data.get("base_score", 0) for data in users_data]
            message_bonuses = [
                data.get("total_messages", 0) * 0.1 for data in users_data
            ]
            response_bonuses = [
                max(0, 10 - data.get("response_time", 0)) * 0.5 for data in users_data
            ]
            activity_bonuses = [data.get("activity_bonus", 0) for data in users_data]

            # ä½¿ç¨ numpy åéåè¨ç®
            self.calculator.performance_service.optimize_calculations(
                base_scores, "sum"
            )
            self.calculator.performance_service.optimize_calculations(
                message_bonuses, "sum"
            )
            self.calculator.performance_service.optimize_calculations(
                response_bonuses, "sum"
            )
            self.calculator.performance_service.optimize_calculations(
                activity_bonuses, "sum"
            )

            # è¨ç®ç¸½åä¸¦éå¶ç¯å
            total_scores = []
            for i in range(len(users_data)):
                total = (
                    base_scores[i]
                    + message_bonuses[i]
                    + response_bonuses[i]
                    + activity_bonuses[i]
                )
                total_scores.append(max(0, min(100, total)))

            return total_scores

        except Exception as e:
            logger.error(f"æ¹éè¨ç®æ´»èºåº¦åæ¸å¤±æ: {e}")
            return [self.calculate_activity_score(data) for data in users_data]

    def batch_update_user_activities(
        self, user_ids: list[str], guild_ids: list[str], activity_types: list[str]
    ) -> list[bool]:
        """
        æ¹éæ´æ°å¤åç¨æ¶çæ´»èºåº¦ (ä½¿ç¨ numpy åªåæ¹éæä½)

        Args:
            user_ids: ç¨æ¶IDåè¡¨
            guild_ids: ä¼ºæå¨IDåè¡¨
            activity_types: æ´»èºåº¦é¡ååè¡¨

        Returns:
            List[bool]: æ´æ°æåçæåè¡¨
        """
        if not user_ids or len(user_ids) != len(guild_ids) != len(activity_types):
            return []

        try:
            results = []
            cache_keys_to_clear = set()

            for user_id, guild_id, activity_type in zip(
                user_ids, guild_ids, activity_types, strict=False
            ):
                success = self.logic_apis.update_user_activity(
                    user_id, guild_id, activity_type
                )
                results.append(success)

                if success:
                    # æ¶ééè¦æ¸é¤çç·©å­éµ
                    cache_keys_to_clear.add(f"activity_{user_id}")
                    cache_keys_to_clear.add(f"leaderboard_{guild_id}")

            # æ¹éæ¸é¤ç·©å­
            for cache_key in cache_keys_to_clear:
                self.cache.delete(cache_key)

            success_count = sum(results)
            logger.info(f"æ¹éæ´»èºåº¦æ´æ°å®æ: {success_count}/{len(user_ids)} æå")

            return results

        except Exception as e:
            logger.error(f"æ¹éæ´»èºåº¦æ´æ°å¤±æ: {e}")
            return [False] * len(user_ids)
