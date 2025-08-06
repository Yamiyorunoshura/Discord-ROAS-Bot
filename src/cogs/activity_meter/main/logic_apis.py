"""
¯ LogicAPIs - ç¨å¼éè¼¯åå¥API
- çºæ¯åç¨å¼éè¼¯åè½æä¾ç¨ç«çAPIæ¥å£
- å¯¦ç¾æ¸æé©è­åé¯èª¤èç
- æ¯æ´æ¬éæª¢æ¥åæ§è½ç£æ§
- æä¾æ¨æºåçAPIé¿ææ ¼å¼
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..database.database import ActivityDatabase
from .calculator import ActivityCalculator
from .renderer import ActivityRenderer

logger = logging.getLogger("logic_apis")


@dataclass
class APIResponse:
    """APIé¿ææ¸æçµæ§"""

    status: str
    data: dict[str, Any | None] = None
    message: str = ""
    timestamp: str = ""
    execution_time: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class LogicAPIs:
    """
    ç¨å¼éè¼¯åå¥API
    - çºæ¯åç¨å¼éè¼¯åè½æä¾ç¨ç«çAPIæ¥å£
    - å¯¦ç¾æ¨æºåçAPIé¿ææ ¼å¼
    - æ¯æ´æ¸æé©è­åé¯èª¤èç
    """

    def __init__(self):
        """åå§åéè¼¯API"""
        self.database = ActivityDatabase()
        self.renderer = ActivityRenderer()
        self.calculator = ActivityCalculator()

        # APIèª¿ç¨çµ±è¨
        self.api_calls = {}
        self.error_counts = {}

        logger.info("LogicAPIs åå§åæå")

    def renderer_logic_api(self, data: dict[str, Any]) -> APIResponse:
        """
        æ¸²æéè¼¯API

        Args:
            data: æ¸²ææ¸æ

        Returns:
            APIResponse: APIé¿æ
        """
        start_time = time.time()

        try:
            # è¨éAPIèª¿ç¨
            self._record_api_call("renderer_logic")

            # é©è­è¼¸å¥æ¸æ
            if not self._validate_render_data(data):
                return APIResponse(
                    status="error",
                    message="æ¸²ææ¸ææ ¼å¼é¯èª¤",
                    execution_time=time.time() - start_time,
                )

            # å·è¡æ¸²æéè¼¯
            rendered_data = self.renderer.render_progress_bar(
                data.get("username", "æªç¥ç¨æ¶"), data.get("score", 0)
            )

            return APIResponse(
                status="success",
                data={"rendered_file": rendered_data},
                message="æ¸²ææå",
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            self._record_error("renderer_logic", str(e))
            logger.error(f"æ¸²æéè¼¯APIå¤±æ: {e}")
            return APIResponse(
                status="error",
                message=f"æ¸²æå¤±æ: {e!s}",
                execution_time=time.time() - start_time,
            )

    def settings_logic_api(self, settings: dict[str, Any]) -> APIResponse:
        """
        è¨­å®éè¼¯API

        Args:
            settings: è¨­å®æ¸æ

        Returns:
            APIResponse: APIé¿æ
        """
        start_time = time.time()

        try:
            # è¨éAPIèª¿ç¨
            self._record_api_call("settings_logic")

            # é©è­è¨­å®æ¸æ
            if not self._validate_settings(settings):
                return APIResponse(
                    status="error",
                    message="è¨­å®æ¸ææ ¼å¼é¯èª¤",
                    execution_time=time.time() - start_time,
                )

            # ä¿å­è¨­å®
            success = self.database.save_settings(settings)

            if success:
                return APIResponse(
                    status="success",
                    message="è¨­å®ä¿å­æå",
                    execution_time=time.time() - start_time,
                )
            else:
                return APIResponse(
                    status="error",
                    message="è¨­å®ä¿å­å¤±æ",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            self._record_error("settings_logic", str(e))
            logger.error(f"è¨­å®éè¼¯APIå¤±æ: {e}")
            return APIResponse(
                status="error",
                message=f"è¨­å®ä¿å­å¤±æ: {e!s}",
                execution_time=time.time() - start_time,
            )

    def get_user_data(self, user_id: str) -> dict[str, Any | None]:
        """
        ç²åç¨æ¶æ¸æ

        Args:
            user_id: ç¨æ¶ID

        Returns:
            Dict[str, Any | None]: ç¨æ¶æ¸æ
        """
        try:
            # è¨éAPIèª¿ç¨
            self._record_api_call("get_user_data")

            # å¾æ¸æåº«ç²åç¨æ¶æ¸æ
            user_data = self.database.get_user_activity(user_id)

            if not user_data:
                return None

            # æ·»å é¡å¤çè¨ç®æ¸æ
            user_data["level"] = self.calculator.calculate_level(
                user_data.get("score", 0)
            )
            user_data["next_level_score"] = self.calculator.get_next_level_score(
                user_data.get("score", 0)
            )

            return user_data

        except Exception as e:
            self._record_error("get_user_data", str(e))
            logger.error(f"ç²åç¨æ¶æ¸æå¤±æ: {user_id}, é¯èª¤: {e}")
            return None

    def get_user_rank(self, user_id: str) -> int | None:
        """
        ç²åç¨æ¶æå

        Args:
            user_id: ç¨æ¶ID

        Returns:
            int | None: ç¨æ¶æå
        """
        try:
            # è¨éAPIèª¿ç¨
            self._record_api_call("get_user_rank")

            # å¾æ¸æåº«ç²åç¨æ¶æå
            rank = self.database.get_user_rank(user_id)

            return rank

        except Exception as e:
            self._record_error("get_user_rank", str(e))
            logger.error(f"ç²åç¨æ¶æåå¤±æ: {user_id}, é¯èª¤: {e}")
            return None

    def get_user_activity_history(
        self, user_id: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        ç²åç¨æ¶æ´»èºåº¦æ­·å²

        Args:
            user_id: ç¨æ¶ID
            days: æ­·å²å¤©æ¸

        Returns:
            List[Dict[str, Any]]: æ´»èºåº¦æ­·å²æ¸æ
        """
        try:
            # è¨éAPIèª¿ç¨
            self._record_api_call("get_user_activity_history")

            # å¾æ¸æåº«ç²åæ­·å²æ¸æ
            history_data = self.database.get_user_activity_history(user_id, days)

            return history_data

        except Exception as e:
            self._record_error("get_user_activity_history", str(e))
            logger.error(f"ç²åæ´»èºåº¦æ­·å²å¤±æ: {user_id}, é¯èª¤: {e}")
            return []

    def get_leaderboard(self, guild_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        ç²åæè¡æ¦

        Args:
            guild_id: ä¼ºæå¨ID
            limit: æè¡æ¦æ¸ééå¶

        Returns:
            List[Dict[str, Any]]: æè¡æ¦æ¸æ
        """
        try:
            # è¨éAPIèª¿ç¨
            self._record_api_call("get_leaderboard")

            # å¾æ¸æåº«ç²åæè¡æ¦æ¸æ
            leaderboard_data = self.database.get_leaderboard(guild_id, limit)

            return leaderboard_data

        except Exception as e:
            self._record_error("get_leaderboard", str(e))
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
            # è¨éAPIèª¿ç¨
            self._record_api_call("update_user_activity")

            # è¨ç®æ°çæ´»èºåº¦åæ¸
            current_score = self.database.get_user_score(user_id, guild_id) or 0
            new_score = self.calculator.calculate_new_score(
                current_score, activity_type
            )

            # æ´æ°æ¸æåº«
            success = self.database.update_user_activity(
                guild_id=guild_id,
                user_id=user_id,
                score=new_score,
                timestamp=int(time.time()),
            )

            return success

        except Exception as e:
            self._record_error("update_user_activity", str(e))
            logger.error(f"æ´æ°ç¨æ¶æ´»èºåº¦å¤±æ: {user_id}, é¯èª¤: {e}")
            return False

    def calculate_activity_score_api(self, user_data: dict[str, Any]) -> APIResponse:
        """
        è¨ç®æ´»èºåº¦åæ¸API

        Args:
            user_data: ç¨æ¶æ¸æ

        Returns:
            APIResponse: APIé¿æ
        """
        start_time = time.time()

        try:
            # è¨éAPIèª¿ç¨
            self._record_api_call("calculate_activity_score")

            # é©è­ç¨æ¶æ¸æ
            if not self._validate_user_data(user_data):
                return APIResponse(
                    status="error",
                    message="ç¨æ¶æ¸ææ ¼å¼é¯èª¤",
                    execution_time=time.time() - start_time,
                )

            # è¨ç®æ´»èºåº¦åæ¸
            score = self.calculator.calculate_score(
                user_data.get("messages", 0), user_data.get("total_messages", 0)
            )

            # è¨ç®ç­ç´
            level = self.calculator.calculate_level(score)

            return APIResponse(
                status="success",
                data={
                    "score": score,
                    "level": level,
                    "next_level_score": self.calculator.get_next_level_score(score),
                },
                message="æ´»èºåº¦åæ¸è¨ç®æå",
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            self._record_error("calculate_activity_score", str(e))
            logger.error(f"è¨ç®æ´»èºåº¦åæ¸å¤±æ: {e}")
            return APIResponse(
                status="error",
                message=f"è¨ç®æ´»èºåº¦åæ¸å¤±æ: {e!s}",
                execution_time=time.time() - start_time,
            )

    def _validate_render_data(self, data: dict[str, Any]) -> bool:
        """
        é©è­æ¸²ææ¸æ

        Args:
            data: æ¸²ææ¸æ

        Returns:
            bool: é©è­æ¯å¦éé
        """
        required_fields = ["username", "score"]
        return all(field in data for field in required_fields)

    def _validate_settings(self, settings: dict[str, Any]) -> bool:
        """
        é©è­è¨­å®æ¸æ

        Args:
            settings: è¨­å®æ¸æ

        Returns:
            bool: é©è­æ¯å¦éé
        """
        required_fields = ["guild_id", "key", "value"]
        return all(field in settings for field in required_fields)

    def _validate_user_data(self, user_data: dict[str, Any]) -> bool:
        """
        é©è­ç¨æ¶æ¸æ

        Args:
            user_data: ç¨æ¶æ¸æ

        Returns:
            bool: é©è­æ¯å¦éé
        """
        required_fields = ["user_id"]
        return all(field in user_data for field in required_fields)

    def _record_api_call(self, api_name: str):
        """è¨éAPIèª¿ç¨"""
        if api_name not in self.api_calls:
            self.api_calls[api_name] = 0
        self.api_calls[api_name] += 1

    def _record_error(self, api_name: str, error_message: str):
        """è¨éé¯èª¤"""
        if api_name not in self.error_counts:
            self.error_counts[api_name] = 0
        self.error_counts[api_name] += 1
        logger.error(f"APIé¯èª¤: {api_name} - {error_message}")

    def get_api_metrics(self) -> dict[str, Any]:
        """
        ç²åAPIææ¨

        Returns:
            Dict[str, Any]: APIææ¨æ¸æ
        """
        return {
            "api_calls": self.api_calls,
            "error_counts": self.error_counts,
            "success_rates": self._calculate_success_rates(),
        }

    def _calculate_success_rates(self) -> dict[str, float]:
        """è¨ç®æåç"""
        success_rates = {}
        for api_name in self.api_calls:
            total_calls = self.api_calls[api_name]
            errors = self.error_counts.get(api_name, 0)
            success_rates[api_name] = (
                ((total_calls - errors) / total_calls * 100) if total_calls > 0 else 0
            )
        return success_rates
