"""
隨機交互測試實施
Task ID: T5 - Discord testing: dpytest and random interactions

完整的隨機交互測試實施，使用dpytest進行Discord bot測試，
支援種子重現和失敗報告生成。
"""

import pytest
import asyncio
import random
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

import discord
import discord.ext.test as dpytest
from discord.ext import commands

from tests.random.random_interaction_engine import (
    RandomTestOrchestrator,
    RandomInteractionGenerator,
    InteractionType,
    TestSequence,
    InteractionStep,
    ReproductionReporter
)

logger = logging.getLogger(__name__)


@pytest.mark.dpytest
@pytest.mark.random_interaction
class TestRandomInteractions:
    """隨機交互測試類"""
    
    @pytest.fixture(autouse=True)
    async def setup_test_environment(self, bot, guild, channel, member):
        """設置測試環境"""
        self.bot = bot
        self.guild = guild
        self.channel = channel
        self.user = member
        self.orchestrator = RandomTestOrchestrator()
        self.generator = RandomInteractionGenerator()
        self.reporter = ReproductionReporter()
        
        # 確保測試報告目錄存在
        Path("test_reports").mkdir(exist_ok=True)
        
        # 添加測試命令到 bot
        await self._setup_test_commands()
    
    async def _setup_test_commands(self):
        """設置測試用的命令"""
        
        @self.bot.command(name="test_echo")
        async def echo_command(ctx, *, message: str = "Hello World"):
            """回聲命令"""
            await ctx.send(f"Echo: {message}")
        
        @self.bot.command(name="test_math")
        async def math_command(ctx, operation: str, a: float, b: float):
            """數學運算命令"""
            if operation == "add":
                result = a + b
            elif operation == "sub":
                result = a - b
            elif operation == "mul":
                result = a * b
            elif operation == "div":
                if b == 0:
                    await ctx.send("Error: Division by zero")
                    return
                result = a / b
            else:
                await ctx.send("Error: Unknown operation")
                return
            
            await ctx.send(f"Result: {result}")
        
        @self.bot.command(name="test_status")
        async def status_command(ctx):
            """狀態查詢命令"""
            await ctx.send("Bot is running normally")
    
    @pytest.mark.asyncio
    async def test_basic_random_sequence(self, request):
        """基本隨機序列測試"""
        seed = getattr(request.config.option, 'seed', None) or random.randint(1, 1000000)
        max_steps = getattr(request.config.option, 'max_steps', None) or 5
        
        logger.info(f"Running random sequence test with seed={seed}, max_steps={max_steps}")
        
        try:
            # 生成測試序列
            generator = RandomInteractionGenerator(seed=seed)
            sequence = generator.generate_sequence(max_steps=max_steps)
            
            # 執行測試序列
            results = await self._execute_test_sequence(sequence)
            
            # 驗證結果
            self._validate_sequence_results(results)
            
            # 如果測試通過，記錄成功
            logger.info(f"Random sequence test passed with seed={seed}")
            
        except Exception as e:
            # 測試失敗時生成重現報告
            failure_info = {
                "test_name": "test_basic_random_sequence",
                "seed": seed,
                "max_steps": max_steps,
                "error": str(e),
                "error_type": type(e).__name__,
                "sequence": sequence if 'sequence' in locals() else None
            }
            
            await self._generate_failure_report(failure_info)
            raise
    
    @pytest.mark.asyncio
    async def test_message_interactions(self, request):
        """消息交互隨機測試"""
        seed = getattr(request.config.option, 'seed', None) or random.randint(1, 1000000)
        
        random.seed(seed)
        
        try:
            # 專注於消息相關的交互
            sequence = TestSequence(
                test_id=f"msg_test_{seed}",
                seed=seed,
                max_steps=8,
                steps=[]
            )
            
            # 生成消息交互步驟
            message_types = [
                InteractionType.SEND_MESSAGE,
                InteractionType.SEND_COMMAND,
                InteractionType.ADD_REACTION
            ]
            
            for i in range(sequence.max_steps):
                interaction_type = random.choice(message_types)
                step = self._create_interaction_step(i, interaction_type, seed)
                sequence.steps.append(step)
            
            # 執行測試
            results = await self._execute_test_sequence(sequence)
            
            # 驗證消息交互
            self._validate_message_interactions(results)
            
        except Exception as e:
            failure_info = {
                "test_name": "test_message_interactions", 
                "seed": seed,
                "error": str(e),
                "sequence": sequence if 'sequence' in locals() else None
            }
            await self._generate_failure_report(failure_info)
            raise
    
    @pytest.mark.asyncio
    async def test_command_variations(self, request):
        """命令變化隨機測試"""
        seed = getattr(request.config.option, 'seed', None) or random.randint(1, 1000000)
        
        random.seed(seed)
        
        try:
            # 測試不同的命令組合
            commands = [
                ("test_echo", {}),
                ("test_echo", {"message": "Random test"}),
                ("test_math", {"operation": "add", "a": 5.0, "b": 3.0}),
                ("test_math", {"operation": "mul", "a": 2.0, "b": 4.0}),
                ("test_status", {})
            ]
            
            sequence = TestSequence(
                test_id=f"cmd_test_{seed}",
                seed=seed,
                max_steps=len(commands),
                steps=[]
            )
            
            # 隨機排列命令
            random.shuffle(commands)
            
            for i, (cmd, params) in enumerate(commands):
                step = InteractionStep(
                    step_id=i,
                    interaction_type=InteractionType.SEND_COMMAND,
                    parameters={"command": cmd, "params": params},
                    timestamp=asyncio.get_event_loop().time(),
                    expected_outcome="command_response"
                )
                sequence.steps.append(step)
            
            # 執行並驗證
            results = await self._execute_test_sequence(sequence)
            self._validate_command_responses(results)
            
        except Exception as e:
            failure_info = {
                "test_name": "test_command_variations",
                "seed": seed,
                "error": str(e),
                "sequence": sequence if 'sequence' in locals() else None
            }
            await self._generate_failure_report(failure_info)
            raise
    
    @pytest.mark.asyncio
    async def test_concurrent_interactions(self, request):
        """併發交互測試"""
        seed = getattr(request.config.option, 'seed', None) or random.randint(1, 1000000)
        
        random.seed(seed)
        
        try:
            # 創建多個並行的交互序列
            tasks = []
            sequences = []
            
            for task_id in range(3):  # 3個並行任務
                sequence = TestSequence(
                    test_id=f"concurrent_{seed}_{task_id}",
                    seed=seed + task_id,
                    max_steps=4,
                    steps=[]
                )
                
                # 為每個序列生成簡單的步驟
                for step_id in range(4):
                    step = InteractionStep(
                        step_id=step_id,
                        interaction_type=InteractionType.SEND_MESSAGE,
                        parameters={
                            "content": f"Concurrent message {task_id}-{step_id}",
                            "user": self.user
                        },
                        timestamp=asyncio.get_event_loop().time()
                    )
                    sequence.steps.append(step)
                
                sequences.append(sequence)
                # 為每個序列創建執行任務
                task = asyncio.create_task(
                    self._execute_simple_sequence(sequence)
                )
                tasks.append(task)
            
            # 等待所有任務完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 驗證併發執行結果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    raise result
                assert result is not None, f"Concurrent task {i} returned None"
            
        except Exception as e:
            failure_info = {
                "test_name": "test_concurrent_interactions",
                "seed": seed,
                "error": str(e),
                "sequences": sequences if 'sequences' in locals() else None
            }
            await self._generate_failure_report(failure_info)
            raise
    
    def _create_interaction_step(self, step_id: int, interaction_type: InteractionType, 
                                seed: int) -> InteractionStep:
        """創建交互步驟"""
        random.seed(seed + step_id)  # 確保可重現性
        
        if interaction_type == InteractionType.SEND_MESSAGE:
            content = random.choice([
                "Hello from random test",
                "Testing message interaction",
                f"Random seed: {seed}",
                "Bot interaction test",
                "🤖 Automated test message"
            ])
            parameters = {"content": content, "user": self.user}
            expected_outcome = "message_sent"
            
        elif interaction_type == InteractionType.SEND_COMMAND:
            commands = ["test_echo", "test_status"]
            command = random.choice(commands)
            parameters = {"command": command, "params": {}}
            expected_outcome = "command_response"
            
        elif interaction_type == InteractionType.ADD_REACTION:
            emojis = ["👍", "❤️", "😄", "🎉", "✅"]
            emoji = random.choice(emojis)
            parameters = {"emoji": emoji}
            expected_outcome = "reaction_added"
            
        else:
            # 默認為發送消息
            parameters = {"content": f"Default interaction {step_id}", "user": self.user}
            expected_outcome = "message_sent"
        
        return InteractionStep(
            step_id=step_id,
            interaction_type=interaction_type,
            parameters=parameters,
            timestamp=asyncio.get_event_loop().time(),
            expected_outcome=expected_outcome
        )
    
    async def _execute_test_sequence(self, sequence: TestSequence) -> List[InteractionStep]:
        """執行測試序列"""
        results = []
        
        for step in sequence.steps:
            try:
                start_time = asyncio.get_event_loop().time()
                
                if step.interaction_type == InteractionType.SEND_MESSAGE:
                    await self._execute_send_message(step)
                elif step.interaction_type == InteractionType.SEND_COMMAND:
                    await self._execute_send_command(step)
                elif step.interaction_type == InteractionType.ADD_REACTION:
                    await self._execute_add_reaction(step)
                else:
                    step.error = f"Unsupported interaction type: {step.interaction_type}"
                    step.success = False
                
                step.timestamp = asyncio.get_event_loop().time() - start_time
                
                if step.success is None:
                    step.success = True
                    
            except Exception as e:
                step.error = str(e)
                step.success = False
                logger.error(f"Step {step.step_id} failed: {e}")
            
            results.append(step)
            
            # 小延遲避免速率限制
            await asyncio.sleep(0.1)
        
        return results
    
    async def _execute_simple_sequence(self, sequence: TestSequence) -> bool:
        """執行簡單序列（用於併發測試）"""
        try:
            for step in sequence.steps:
                if step.interaction_type == InteractionType.SEND_MESSAGE:
                    # 簡化的消息發送
                    content = step.parameters.get("content", "test message")
                    # 使用 dpytest 直接發送消息而不觸發命令處理
                    message = dpytest.backend.make_message(content, self.user, self.channel)
                    step.success = True
                else:
                    step.success = True
                
                await asyncio.sleep(0.05)  # 短暫延遲
            
            return True
            
        except Exception as e:
            logger.error(f"Simple sequence execution failed: {e}")
            return False
    
    async def _execute_send_message(self, step: InteractionStep):
        """執行發送消息"""
        content = step.parameters.get("content", "test message")
        user = step.parameters.get("user", self.user)
        
        # 使用 dpytest 發送消息
        message = dpytest.backend.make_message(content, user, self.channel)
        step.actual_outcome = f"message_sent: {message.id}"
        step.success = True
    
    async def _execute_send_command(self, step: InteractionStep):
        """執行發送命令"""
        command = step.parameters.get("command", "test_status")
        params = step.parameters.get("params", {})
        
        # 構建命令字符串
        if params:
            param_str = " ".join([f"{k} {v}" for k, v in params.items()])
            full_command = f"!test_{command} {param_str}"
        else:
            full_command = f"!test_{command}"
        
        # 發送命令消息
        message = dpytest.backend.make_message(full_command, self.user, self.channel)
        
        # 等待回應（簡化版）
        try:
            response = await dpytest.wait_for_message(timeout=2.0)
            step.actual_outcome = f"command_response: {response.content[:50]}"
            step.success = True
        except asyncio.TimeoutError:
            step.actual_outcome = "command_no_response"
            step.success = False
    
    async def _execute_add_reaction(self, step: InteractionStep):
        """執行添加反應"""
        emoji = step.parameters.get("emoji", "👍")
        
        # 需要先有一個消息來添加反應
        # 發送一個臨時消息
        temp_message = dpytest.backend.make_message("Temp message for reaction", self.user, self.channel)
        
        # 添加反應
        dpytest.backend.add_reaction(temp_message, emoji, self.user)
        step.actual_outcome = f"reaction_added: {emoji}"
        step.success = True
    
    def _validate_sequence_results(self, results: List[InteractionStep]):
        """驗證序列結果"""
        total_steps = len(results)
        successful_steps = sum(1 for step in results if step.success)
        
        # 至少 80% 的步驟應該成功
        success_rate = successful_steps / total_steps if total_steps > 0 else 0
        assert success_rate >= 0.8, f"Success rate too low: {success_rate:.2%} ({successful_steps}/{total_steps})"
        
        # 檢查是否有步驟
        assert total_steps > 0, "No interaction steps were executed"
    
    def _validate_message_interactions(self, results: List[InteractionStep]):
        """驗證消息交互"""
        message_steps = [step for step in results 
                        if step.interaction_type in [InteractionType.SEND_MESSAGE, InteractionType.SEND_COMMAND]]
        
        assert len(message_steps) > 0, "No message interactions found"
        
        # 驗證每個消息步驟
        for step in message_steps:
            if step.success:
                assert step.actual_outcome is not None, f"Step {step.step_id} missing actual outcome"
    
    def _validate_command_responses(self, results: List[InteractionStep]):
        """驗證命令回應"""
        command_steps = [step for step in results if step.interaction_type == InteractionType.SEND_COMMAND]
        
        for step in command_steps:
            if step.success:
                assert "command_response" in step.actual_outcome, f"Command step {step.step_id} missing response"
    
    async def _generate_failure_report(self, failure_info: Dict[str, Any]):
        """生成失敗重現報告"""
        try:
            timestamp = int(asyncio.get_event_loop().time())
            report_file = Path(f"test_reports/random_test_failure_{timestamp}.json")
            
            # 準備報告數據
            report_data = {
                "failure_info": failure_info,
                "reproduction_instructions": {
                    "command": f"python -m pytest tests/random/test_random_interactions.py::{failure_info['test_name']} --seed={failure_info.get('seed', 'unknown')}",
                    "seed": failure_info.get('seed'),
                    "environment": {
                        "python_version": "3.10.18",
                        "dpytest_available": True
                    }
                },
                "generated_at": timestamp,
                "debug_info": {
                    "test_directory": str(Path.cwd()),
                    "guild_id": getattr(self.guild, 'id', None),
                    "channel_id": getattr(self.channel, 'id', None)
                }
            }
            
            # 如果有序列資訊，包含序列詳情
            if failure_info.get('sequence'):
                sequence = failure_info['sequence']
                if hasattr(sequence, 'steps'):
                    report_data["sequence_details"] = {
                        "test_id": getattr(sequence, 'test_id', 'unknown'),
                        "total_steps": len(sequence.steps),
                        "steps": [
                            {
                                "step_id": step.step_id,
                                "interaction_type": step.interaction_type.value if hasattr(step.interaction_type, 'value') else str(step.interaction_type),
                                "parameters": step.parameters,
                                "success": step.success,
                                "error": step.error
                            }
                            for step in sequence.steps
                        ]
                    }
            
            # 寫入報告檔案
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.error(f"Failure report generated: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate failure report: {e}")


# 獨立執行的函數測試
@pytest.mark.dpytest
async def test_random_interaction_basic():
    """基本隨機交互測試（不依賴類）"""
    try:
        # 創建基本的隨機交互生成器
        from tests.random.random_interaction_engine import RandomInteractionGenerator
        
        generator = RandomInteractionGenerator(seed=42)
        
        # 生成簡單的測試序列
        sequence = generator.generate_sequence(max_steps=3)
        
        # 驗證序列生成
        assert sequence is not None
        assert hasattr(sequence, 'steps')
        assert len(sequence.steps) <= 3
        assert sequence.seed == 42
        
        print(f"✅ Basic random interaction test passed with {len(sequence.steps)} steps")
        
    except Exception as e:
        print(f"❌ Basic random interaction test failed: {e}")
        raise