"""
隨機交互測試引擎
Task ID: T5 - Discord testing: dpytest and random interactions

提供可重現的隨機測試場景生成與執行，包含種子管理和失敗重現機制。
"""

import random
import json
import time
import asyncio
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """交互類型枚舉"""
    SEND_MESSAGE = "send_message"
    SEND_COMMAND = "send_command"
    ADD_REACTION = "add_reaction"
    JOIN_VOICE = "join_voice"
    LEAVE_VOICE = "leave_voice"
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"
    CREATE_THREAD = "create_thread"
    PIN_MESSAGE = "pin_message"
    UNPIN_MESSAGE = "unpin_message"


@dataclass
class InteractionStep:
    """單個交互步驟"""
    step_id: int
    interaction_type: InteractionType
    parameters: Dict[str, Any]
    timestamp: float
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    success: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class TestSequence:
    """測試序列"""
    sequence_id: str
    seed: int
    max_steps: int
    steps: List[InteractionStep]
    start_time: float
    end_time: Optional[float] = None
    success: Optional[bool] = None
    failure_step: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class SeedManager:
    """種子管理器"""
    
    @staticmethod
    def generate_seed() -> int:
        """生成隨機種子"""
        return random.randint(1, 2**31 - 1)
    
    @staticmethod
    def validate_seed(seed: Union[int, str]) -> int:
        """
        驗證並轉換種子
        
        Args:
            seed: 種子值（整數或字串）
            
        Returns:
            驗證後的種子整數
            
        Raises:
            ValueError: 種子無效
        """
        try:
            seed_int = int(seed)
            if not (1 <= seed_int <= 2**31 - 1):
                raise ValueError(f"種子必須在 1 到 {2**31 - 1} 之間")
            return seed_int
        except (ValueError, TypeError) as e:
            raise ValueError(f"無效的種子格式: {seed}") from e
    
    @staticmethod
    def set_global_seed(seed: int) -> None:
        """設定全域隨機種子"""
        random.seed(seed)
        logger.info(f"設定隨機種子: {seed}")


class RandomInteractionGenerator:
    """隨機交互生成器"""
    
    def __init__(self, seed: Optional[int] = None):
        """
        初始化生成器
        
        Args:
            seed: 隨機種子（可選）
        """
        self.seed = seed or SeedManager.generate_seed()
        self.rng = random.Random(self.seed)
        
        # 交互類型權重配置
        self.interaction_weights = {
            InteractionType.SEND_MESSAGE: 30,
            InteractionType.SEND_COMMAND: 20,
            InteractionType.ADD_REACTION: 15,
            InteractionType.EDIT_MESSAGE: 10,
            InteractionType.DELETE_MESSAGE: 8,
            InteractionType.JOIN_VOICE: 5,
            InteractionType.LEAVE_VOICE: 5,
            InteractionType.CREATE_THREAD: 3,
            InteractionType.PIN_MESSAGE: 2,
            InteractionType.UNPIN_MESSAGE: 2
        }
        
        # 測試資料池
        self.test_messages = [
            "Hello world!",
            "這是一個測試訊息",
            "Random test content",
            "🎉 表情符號測試",
            "多行\n訊息\n測試",
            "Special chars: !@#$%^&*()",
            "Very long message " + "x" * 200,
            "",  # 空訊息
            "   ",  # 空白訊息
        ]
        
        self.test_commands = [
            "help",
            "ping",
            "status",
            "achievements",
            "profile",
            "admin status",
            "test random",
            "nonexistent",
        ]
        
        self.test_emojis = ["👍", "👎", "❤️", "😂", "😢", "🎉", "✅", "❌"]
    
    def generate_sequence(self, max_steps: int) -> TestSequence:
        """
        生成隨機測試序列
        
        Args:
            max_steps: 最大步驟數
            
        Returns:
            生成的測試序列
        """
        sequence_id = str(uuid.uuid4())
        steps = []
        
        logger.info(f"生成隨機序列 {sequence_id}，種子: {self.seed}，最大步驟: {max_steps}")
        
        # 設定狀態追蹤
        sent_messages = []
        current_voice_state = False
        pinned_messages = []
        
        for step_id in range(max_steps):
            interaction_type = self._choose_interaction_type()
            parameters = self._generate_interaction_parameters(
                interaction_type, sent_messages, current_voice_state, pinned_messages
            )
            
            step = InteractionStep(
                step_id=step_id,
                interaction_type=interaction_type,
                parameters=parameters,
                timestamp=time.time(),
                expected_outcome=self._predict_outcome(interaction_type, parameters)
            )
            
            steps.append(step)
            
            # 更新狀態追蹤
            self._update_state_tracking(
                interaction_type, parameters, sent_messages, 
                current_voice_state, pinned_messages
            )
        
        return TestSequence(
            sequence_id=sequence_id,
            seed=self.seed,
            max_steps=max_steps,
            steps=steps,
            start_time=time.time(),
            metadata={
                "generator_version": "1.0",
                "interaction_weights": self.interaction_weights
            }
        )
    
    def _choose_interaction_type(self) -> InteractionType:
        """根據權重選擇交互類型"""
        types = list(self.interaction_weights.keys())
        weights = list(self.interaction_weights.values())
        return self.rng.choices(types, weights=weights)[0]
    
    def _generate_interaction_parameters(
        self, 
        interaction_type: InteractionType,
        sent_messages: List[Dict],
        current_voice_state: bool,
        pinned_messages: List[Dict]
    ) -> Dict[str, Any]:
        """
        生成交互參數
        
        Args:
            interaction_type: 交互類型
            sent_messages: 已發送的訊息列表
            current_voice_state: 當前語音狀態
            pinned_messages: 已釘選的訊息列表
            
        Returns:
            交互參數字典
        """
        if interaction_type == InteractionType.SEND_MESSAGE:
            return {
                "content": self.rng.choice(self.test_messages),
                "channel": "general"
            }
        
        elif interaction_type == InteractionType.SEND_COMMAND:
            return {
                "command": self.rng.choice(self.test_commands),
                "channel": "general"
            }
        
        elif interaction_type == InteractionType.ADD_REACTION:
            if sent_messages:
                target_message = self.rng.choice(sent_messages)
                return {
                    "message_id": target_message["id"],
                    "emoji": self.rng.choice(self.test_emojis),
                    "channel": target_message["channel"]
                }
            else:
                # 如果沒有訊息可反應，改為發送訊息
                return {
                    "content": "No messages to react to",
                    "channel": "general"
                }
        
        elif interaction_type == InteractionType.EDIT_MESSAGE:
            if sent_messages:
                target_message = self.rng.choice(sent_messages)
                return {
                    "message_id": target_message["id"],
                    "new_content": f"編輯: {self.rng.choice(self.test_messages)}",
                    "channel": target_message["channel"]
                }
            else:
                return {"content": "No messages to edit", "channel": "general"}
        
        elif interaction_type == InteractionType.DELETE_MESSAGE:
            if sent_messages:
                target_message = self.rng.choice(sent_messages)
                return {
                    "message_id": target_message["id"],
                    "channel": target_message["channel"]
                }
            else:
                return {"content": "No messages to delete", "channel": "general"}
        
        elif interaction_type == InteractionType.JOIN_VOICE:
            return {
                "channel": "一般語音",
                "already_connected": current_voice_state
            }
        
        elif interaction_type == InteractionType.LEAVE_VOICE:
            return {
                "currently_connected": current_voice_state
            }
        
        elif interaction_type == InteractionType.CREATE_THREAD:
            return {
                "name": f"隨機討論串 {self.rng.randint(1, 1000)}",
                "channel": "general"
            }
        
        elif interaction_type == InteractionType.PIN_MESSAGE:
            if sent_messages and len(pinned_messages) < 50:  # Discord 限制
                unpinned_messages = [m for m in sent_messages if m["id"] not in [p["id"] for p in pinned_messages]]
                if unpinned_messages:
                    target_message = self.rng.choice(unpinned_messages)
                    return {
                        "message_id": target_message["id"],
                        "channel": target_message["channel"]
                    }
            return {"content": "Cannot pin message", "channel": "general"}
        
        elif interaction_type == InteractionType.UNPIN_MESSAGE:
            if pinned_messages:
                target_message = self.rng.choice(pinned_messages)
                return {
                    "message_id": target_message["id"],
                    "channel": target_message["channel"]
                }
            return {"content": "No messages to unpin", "channel": "general"}
        
        else:
            return {}
    
    def _predict_outcome(self, interaction_type: InteractionType, parameters: Dict[str, Any]) -> str:
        """預測交互結果"""
        if interaction_type == InteractionType.SEND_MESSAGE:
            if not parameters.get("content"):
                return "empty_message_error"
            return "message_sent"
        
        elif interaction_type == InteractionType.SEND_COMMAND:
            command = parameters.get("command", "")
            if command in ["help", "ping", "status"]:
                return "command_success"
            elif command == "nonexistent":
                return "command_not_found"
            else:
                return "command_processed"
        
        elif interaction_type == InteractionType.ADD_REACTION:
            if "message_id" in parameters:
                return "reaction_added"
            return "reaction_failed"
        
        elif interaction_type == InteractionType.JOIN_VOICE:
            if parameters.get("already_connected"):
                return "already_in_voice"
            return "voice_joined"
        
        elif interaction_type == InteractionType.LEAVE_VOICE:
            if not parameters.get("currently_connected"):
                return "not_in_voice"
            return "voice_left"
        
        else:
            return "unknown_outcome"
    
    def _update_state_tracking(
        self,
        interaction_type: InteractionType,
        parameters: Dict[str, Any],
        sent_messages: List[Dict],
        current_voice_state: bool,
        pinned_messages: List[Dict]
    ) -> None:
        """更新狀態追蹤"""
        if interaction_type == InteractionType.SEND_MESSAGE:
            message_id = f"msg_{len(sent_messages)}"
            sent_messages.append({
                "id": message_id,
                "content": parameters.get("content"),
                "channel": parameters.get("channel")
            })
        
        elif interaction_type == InteractionType.DELETE_MESSAGE:
            message_id = parameters.get("message_id")
            sent_messages[:] = [m for m in sent_messages if m["id"] != message_id]
            pinned_messages[:] = [m for m in pinned_messages if m["id"] != message_id]
        
        elif interaction_type == InteractionType.PIN_MESSAGE:
            message_id = parameters.get("message_id")
            message = next((m for m in sent_messages if m["id"] == message_id), None)
            if message and message not in pinned_messages:
                pinned_messages.append(message)
        
        elif interaction_type == InteractionType.UNPIN_MESSAGE:
            message_id = parameters.get("message_id")
            pinned_messages[:] = [m for m in pinned_messages if m["id"] != message_id]


class RandomTestOrchestrator:
    """隨機測試協調器"""
    
    def __init__(self):
        """初始化協調器"""
        self.current_sequence: Optional[TestSequence] = None
        self.execution_results: List[TestSequence] = []
    
    async def execute_sequence(self, sequence: TestSequence) -> TestSequence:
        """
        執行測試序列
        
        Args:
            sequence: 要執行的測試序列
            
        Returns:
            執行結果更新後的序列
        """
        self.current_sequence = sequence
        sequence.start_time = time.time()
        
        logger.info(f"開始執行序列 {sequence.sequence_id}，共 {len(sequence.steps)} 步驟")
        
        try:
            for step in sequence.steps:
                success = await self._execute_step(step)
                step.success = success
                
                if not success:
                    sequence.failure_step = step.step_id
                    sequence.success = False
                    logger.warning(f"步驟 {step.step_id} 執行失敗: {step.error}")
                    break
            else:
                sequence.success = True
                logger.info(f"序列 {sequence.sequence_id} 執行成功")
        
        except Exception as e:
            sequence.success = False
            logger.error(f"序列執行出現異常: {e}")
        
        finally:
            sequence.end_time = time.time()
            self.execution_results.append(sequence)
        
        return sequence
    
    async def _execute_step(self, step: InteractionStep) -> bool:
        """
        執行單個步驟
        
        Args:
            step: 要執行的步驟
            
        Returns:
            執行是否成功
        """
        try:
            logger.debug(f"執行步驟 {step.step_id}: {step.interaction_type.value}")
            
            # 模擬執行延遲
            await asyncio.sleep(0.1)
            
            # 這裡應該整合 dpytest 或實際的 Discord 互動
            # 目前作為模擬實作
            if step.interaction_type == InteractionType.SEND_MESSAGE:
                step.actual_outcome = "message_sent"
                return True
            
            elif step.interaction_type == InteractionType.SEND_COMMAND:
                command = step.parameters.get("command", "")
                if command == "nonexistent":
                    step.actual_outcome = "command_not_found"
                    step.error = "命令不存在"
                    return False
                else:
                    step.actual_outcome = "command_processed"
                    return True
            
            elif step.interaction_type == InteractionType.ADD_REACTION:
                if "message_id" in step.parameters:
                    step.actual_outcome = "reaction_added"
                    return True
                else:
                    step.actual_outcome = "reaction_failed"
                    step.error = "找不到目標訊息"
                    return False
            
            else:
                # 其他類型的模擬實作
                step.actual_outcome = "simulated_success"
                return True
        
        except Exception as e:
            step.error = str(e)
            step.actual_outcome = "exception"
            logger.error(f"步驟執行異常: {e}")
            return False
    
    def get_results(self) -> List[TestSequence]:
        """取得執行結果"""
        return self.execution_results.copy()
    
    def clear_results(self) -> None:
        """清除執行結果"""
        self.execution_results.clear()


class ReproductionReporter:
    """重現報告生成器"""
    
    @staticmethod
    def generate_report(sequence: TestSequence, output_dir: Path = None) -> Dict[str, Any]:
        """
        生成重現報告
        
        Args:
            sequence: 測試序列
            output_dir: 輸出目錄（可選）
            
        Returns:
            報告字典
        """
        report = {
            "reproduction_info": {
                "sequence_id": sequence.sequence_id,
                "seed": sequence.seed,
                "max_steps": sequence.max_steps,
                "reproduction_command": f"pytest tests/random/ --seed={sequence.seed} --max-steps={sequence.max_steps}",
                "timestamp": time.time(),
                "success": sequence.success,
                "failure_step": sequence.failure_step
            },
            "execution_summary": {
                "total_steps": len(sequence.steps),
                "successful_steps": len([s for s in sequence.steps if s.success]),
                "failed_steps": len([s for s in sequence.steps if s.success is False]),
                "execution_time": sequence.end_time - sequence.start_time if sequence.end_time else None
            },
            "steps": [asdict(step) for step in sequence.steps],
            "metadata": sequence.metadata or {}
        }
        
        # 如果有失敗，添加詳細失敗資訊
        if not sequence.success and sequence.failure_step is not None:
            failed_step = sequence.steps[sequence.failure_step]
            report["failure_analysis"] = {
                "failed_step_id": sequence.failure_step,
                "failed_interaction": failed_step.interaction_type.value,
                "error_message": failed_step.error,
                "expected_outcome": failed_step.expected_outcome,
                "actual_outcome": failed_step.actual_outcome,
                "reproduction_snippet": ReproductionReporter._generate_reproduction_snippet(sequence, sequence.failure_step)
            }
        
        # 保存到檔案
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"random_test_reproduction_{sequence.sequence_id[:8]}.json"
            filepath = output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"重現報告已保存至: {filepath}")
        
        return report
    
    @staticmethod
    def _generate_reproduction_snippet(sequence: TestSequence, failure_step: int) -> str:
        """生成重現程式碼片段"""
        snippet_lines = [
            "# 重現失敗場景的程式碼片段",
            f"import random",
            f"random.seed({sequence.seed})",
            "",
            "# 執行到失敗步驟的操作序列:",
        ]
        
        for i, step in enumerate(sequence.steps[:failure_step + 1]):
            action = step.interaction_type.value
            params = step.parameters
            snippet_lines.append(f"# 步驟 {i}: {action}")
            snippet_lines.append(f"# 參數: {params}")
            
            if i == failure_step:
                snippet_lines.append(f"# --> 此步驟失敗: {step.error}")
        
        return "\n".join(snippet_lines)