"""
多子機器人並行運行負載測試套件
Task ID: 3 - 子機器人聊天功能和管理系統開發

測試多個子機器人同時運行的效能和負載：
- 並發子機器人創建和管理
- 系統資源使用監控
- 網路連線壓力測試
- 記憶體洩漏檢測
- 錯誤率和恢復能力測試
"""

import pytest
import asyncio
import time
import psutil
import resource
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor
import threading
import gc


class SystemResourceMonitor:
    """系統資源監控器"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.initial_memory = None
        self.peak_memory = None
        self.initial_cpu = None
        self.peak_cpu = None
        self.measurements = []
        self.monitoring = False
        self.monitor_task = None
    
    def start_monitoring(self):
        """開始監控系統資源"""
        self.start_time = datetime.now()
        self.initial_memory = self._get_memory_usage()
        self.initial_cpu = self._get_cpu_usage()
        self.peak_memory = self.initial_memory
        self.peak_cpu = self.initial_cpu
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self):
        """停止監控系統資源"""
        self.monitoring = False
        self.end_time = datetime.now()
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self):
        """監控循環"""
        while self.monitoring:
            try:
                memory = self._get_memory_usage()
                cpu = self._get_cpu_usage()
                
                if memory > self.peak_memory:
                    self.peak_memory = memory
                if cpu > self.peak_cpu:
                    self.peak_cpu = cpu
                
                measurement = {
                    'timestamp': datetime.now(),
                    'memory_mb': memory,
                    'cpu_percent': cpu
                }
                self.measurements.append(measurement)
                
                await asyncio.sleep(0.5)  # 每0.5秒監控一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"監控錯誤: {e}")
    
    def _get_memory_usage(self) -> float:
        """獲取記憶體使用量（MB）"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # 轉換為MB
        except:
            return 0.0
    
    def _get_cpu_usage(self) -> float:
        """獲取CPU使用率"""
        try:
            return psutil.cpu_percent()
        except:
            return 0.0
    
    def get_report(self) -> Dict[str, Any]:
        """獲取監控報告"""
        if not self.start_time or not self.end_time:
            return {}
        
        duration = (self.end_time - self.start_time).total_seconds()
        memory_increase = self.peak_memory - self.initial_memory
        
        return {
            'duration_seconds': duration,
            'initial_memory_mb': self.initial_memory,
            'peak_memory_mb': self.peak_memory,
            'memory_increase_mb': memory_increase,
            'initial_cpu_percent': self.initial_cpu,
            'peak_cpu_percent': self.peak_cpu,
            'total_measurements': len(self.measurements),
            'average_memory_mb': sum(m['memory_mb'] for m in self.measurements) / len(self.measurements) if self.measurements else 0,
            'average_cpu_percent': sum(m['cpu_percent'] for m in self.measurements) / len(self.measurements) if self.measurements else 0,
        }


class LoadTestSubBotService:
    """負載測試用的子機器人服務模擬"""
    
    def __init__(self, max_bots: int = 50, failure_rate: float = 0.1):
        self.max_bots = max_bots
        self.failure_rate = failure_rate
        self.bots: Dict[str, Dict[str, Any]] = {}
        self.active_connections: Dict[str, Mock] = {}
        self.creation_count = 0
        self.start_count = 0
        self.stop_count = 0
        
        # 模擬延遲和資源使用
        self.creation_delay = 0.1
        self.start_delay = 0.2
        self.stop_delay = 0.1
    
    async def create_sub_bot(self, name: str, token: str, target_channels: List[int], **kwargs) -> str:
        """創建子機器人"""
        await asyncio.sleep(self.creation_delay)
        
        if len(self.bots) >= self.max_bots:
            raise Exception(f"已達最大子機器人數量限制: {self.max_bots}")
        
        # 模擬隨機失敗
        import random
        if random.random() < self.failure_rate:
            raise Exception("創建失敗：模擬隨機錯誤")
        
        bot_id = f"load_test_bot_{self.creation_count}_{int(time.time() * 1000)}"
        self.creation_count += 1
        
        self.bots[bot_id] = {
            'bot_id': bot_id,
            'name': name,
            'token_hash': f"encrypted_{token}",
            'target_channels': target_channels,
            'status': 'offline',
            'created_at': datetime.now(),
            'message_count': 0,
            **kwargs
        }
        
        return bot_id
    
    async def start_sub_bot(self, bot_id: str) -> bool:
        """啟動子機器人"""
        await asyncio.sleep(self.start_delay)
        
        if bot_id not in self.bots:
            raise Exception(f"子機器人不存在: {bot_id}")
        
        # 模擬隨機失敗
        import random
        if random.random() < self.failure_rate:
            raise Exception("啟動失敗：模擬隨機錯誤")
        
        self.start_count += 1
        self.bots[bot_id]['status'] = 'online'
        
        # 模擬Discord連線
        self.active_connections[bot_id] = Mock()
        
        return True
    
    async def stop_sub_bot(self, bot_id: str) -> bool:
        """停止子機器人"""
        await asyncio.sleep(self.stop_delay)
        
        if bot_id not in self.bots:
            return False
        
        self.stop_count += 1
        self.bots[bot_id]['status'] = 'offline'
        
        if bot_id in self.active_connections:
            del self.active_connections[bot_id]
        
        return True
    
    async def delete_sub_bot(self, bot_id: str) -> bool:
        """刪除子機器人"""
        if bot_id not in self.bots:
            return False
        
        if bot_id in self.active_connections:
            await self.stop_sub_bot(bot_id)
        
        del self.bots[bot_id]
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        online_bots = sum(1 for bot in self.bots.values() if bot['status'] == 'online')
        return {
            'total_bots': len(self.bots),
            'online_bots': online_bots,
            'offline_bots': len(self.bots) - online_bots,
            'active_connections': len(self.active_connections),
            'creation_count': self.creation_count,
            'start_count': self.start_count,
            'stop_count': self.stop_count
        }


class LoadTestChannelService:
    """負載測試用的頻道管理服務模擬"""
    
    def __init__(self, max_channels_per_bot: int = 10):
        self.max_channels_per_bot = max_channels_per_bot
        self.channel_assignments: Dict[str, List[int]] = {}
        self.channel_conflicts: Dict[int, List[str]] = {}
    
    async def assign_channels(self, bot_id: str, channels: List[int]) -> bool:
        """分配頻道"""
        await asyncio.sleep(0.05)  # 模擬處理延遲
        
        if len(channels) > self.max_channels_per_bot:
            raise Exception(f"頻道數量超過限制: {self.max_channels_per_bot}")
        
        self.channel_assignments[bot_id] = channels
        
        for channel_id in channels:
            if channel_id not in self.channel_conflicts:
                self.channel_conflicts[channel_id] = []
            if bot_id not in self.channel_conflicts[channel_id]:
                self.channel_conflicts[channel_id].append(bot_id)
        
        return True
    
    async def unassign_channels(self, bot_id: str, channels: Optional[List[int]] = None) -> bool:
        """取消頻道分配"""
        await asyncio.sleep(0.05)
        
        if bot_id not in self.channel_assignments:
            return False
        
        if channels is None:
            channels = self.channel_assignments[bot_id].copy()
        
        # 更新衝突映射
        for channel_id in channels:
            if channel_id in self.channel_conflicts:
                if bot_id in self.channel_conflicts[channel_id]:
                    self.channel_conflicts[channel_id].remove(bot_id)
                if not self.channel_conflicts[channel_id]:
                    del self.channel_conflicts[channel_id]
        
        if channels == self.channel_assignments[bot_id]:
            del self.channel_assignments[bot_id]
        else:
            remaining = [ch for ch in self.channel_assignments[bot_id] if ch not in channels]
            self.channel_assignments[bot_id] = remaining
        
        return True


@pytest.fixture
def load_test_subbot_service():
    """負載測試子機器人服務"""
    return LoadTestSubBotService(max_bots=100, failure_rate=0.05)


@pytest.fixture
def load_test_channel_service():
    """負載測試頻道服務"""
    return LoadTestChannelService(max_channels_per_bot=5)


@pytest.fixture
def resource_monitor():
    """資源監控器"""
    monitor = SystemResourceMonitor()
    yield monitor
    if monitor.monitoring:
        asyncio.create_task(monitor.stop_monitoring())


class TestConcurrentBotCreation:
    """並發子機器人創建測試"""
    
    @pytest.mark.asyncio
    async def test_create_multiple_bots_concurrently(self, load_test_subbot_service, resource_monitor):
        """測試並發創建多個子機器人"""
        service = load_test_subbot_service
        resource_monitor.start_monitoring()
        
        async def create_bot(i):
            try:
                bot_id = await service.create_sub_bot(
                    name=f"ConcurrentBot{i}",
                    token=f"token_{i}",
                    target_channels=[123456789 + i],
                    ai_enabled=i % 2 == 0,
                    rate_limit=10
                )
                return {'success': True, 'bot_id': bot_id}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        
        # 並發創建20個子機器人
        start_time = time.time()
        tasks = [create_bot(i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        creation_time = time.time() - start_time
        
        await resource_monitor.stop_monitoring()
        
        # 分析結果
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        assert len(successful) >= 15  # 至少75%成功率（考慮5%失敗率）
        assert creation_time < 5.0  # 創建時間應該在5秒內
        
        # 檢查資源使用
        resource_report = resource_monitor.get_report()
        assert resource_report['memory_increase_mb'] < 100  # 記憶體增長不應超過100MB
        
        print(f"創建結果: 成功={len(successful)}, 失敗={len(failed)}, 耗時={creation_time:.2f}秒")
        print(f"記憶體增長: {resource_report['memory_increase_mb']:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_concurrent_start_stop_operations(self, load_test_subbot_service, resource_monitor):
        """測試並發啟動停止操作"""
        service = load_test_subbot_service
        
        # 首先創建一些子機器人
        bot_ids = []
        for i in range(10):
            bot_id = await service.create_sub_bot(
                name=f"StartStopBot{i}",
                token=f"token_{i}",
                target_channels=[123456789 + i]
            )
            bot_ids.append(bot_id)
        
        resource_monitor.start_monitoring()
        
        # 並發啟動所有子機器人
        start_time = time.time()
        start_tasks = [service.start_sub_bot(bot_id) for bot_id in bot_ids]
        start_results = await asyncio.gather(*start_tasks, return_exceptions=True)
        start_time_elapsed = time.time() - start_time
        
        # 並發停止所有子機器人
        stop_start_time = time.time()
        stop_tasks = [service.stop_sub_bot(bot_id) for bot_id in bot_ids]
        stop_results = await asyncio.gather(*stop_tasks, return_exceptions=True)
        stop_time_elapsed = time.time() - stop_start_time
        
        await resource_monitor.stop_monitoring()
        
        # 分析結果
        successful_starts = [r for r in start_results if r is True]
        successful_stops = [r for r in stop_results if r is True]
        
        assert len(successful_starts) >= 8  # 至少80%的啟動成功
        assert len(successful_stops) >= 8   # 至少80%的停止成功
        assert start_time_elapsed < 3.0     # 啟動時間應該在3秒內
        assert stop_time_elapsed < 2.0      # 停止時間應該在2秒內
        
        print(f"啟動結果: 成功={len(successful_starts)}, 耗時={start_time_elapsed:.2f}秒")
        print(f"停止結果: 成功={len(successful_stops)}, 耗時={stop_time_elapsed:.2f}秒")
    
    @pytest.mark.asyncio 
    async def test_maximum_bot_limit(self, load_test_subbot_service):
        """測試最大子機器人數量限制"""
        service = load_test_subbot_service
        service.max_bots = 25  # 設置較小的限制以便測試
        
        # 創建到限制數量
        created_bots = []
        for i in range(25):
            try:
                bot_id = await service.create_sub_bot(
                    name=f"LimitTestBot{i}",
                    token=f"token_{i}",
                    target_channels=[123456789 + i]
                )
                created_bots.append(bot_id)
            except Exception:
                break  # 遇到錯誤就停止（可能是隨機失敗）
        
        # 檢查已經接近或達到限制
        assert len(created_bots) >= 20  # 考慮隨機失敗，至少創建20個
        
        # 嘗試創建超過限制的子機器人
        with pytest.raises(Exception, match="已達最大子機器人數量限制"):
            await service.create_sub_bot(
                name="ExcessBot",
                token="excess_token",
                target_channels=[999999999]
            )


class TestPerformanceUnderLoad:
    """負載下的效能測試"""
    
    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, load_test_subbot_service, resource_monitor):
        """測試持續負載下的效能"""
        service = load_test_subbot_service
        service.max_bots = 50
        
        resource_monitor.start_monitoring()
        
        # 階段1：創建大量子機器人
        bot_ids = []
        creation_failures = 0
        
        for i in range(40):
            try:
                bot_id = await service.create_sub_bot(
                    name=f"SustainedBot{i}",
                    token=f"sustained_token_{i}",
                    target_channels=[123456789 + i % 10]  # 共享一些頻道
                )
                bot_ids.append(bot_id)
            except Exception:
                creation_failures += 1
                continue
        
        # 階段2：批量啟動
        started_bots = []
        for bot_id in bot_ids[:30]:  # 只啟動前30個
            try:
                success = await service.start_sub_bot(bot_id)
                if success:
                    started_bots.append(bot_id)
            except Exception:
                continue
        
        # 階段3：模擬運行一段時間
        await asyncio.sleep(2.0)
        
        # 階段4：動態停止和重啟部分子機器人
        dynamic_operations = []
        for i in range(10):
            bot_id = started_bots[i % len(started_bots)]
            
            # 停止
            try:
                await service.stop_sub_bot(bot_id)
                dynamic_operations.append(f"stopped_{bot_id}")
            except Exception:
                continue
            
            await asyncio.sleep(0.1)
            
            # 重新啟動
            try:
                await service.start_sub_bot(bot_id)
                dynamic_operations.append(f"restarted_{bot_id}")
            except Exception:
                continue
        
        await resource_monitor.stop_monitoring()
        
        # 獲取最終統計
        stats = service.get_stats()
        resource_report = resource_monitor.get_report()
        
        # 驗證結果
        assert stats['total_bots'] >= 35  # 考慮失敗率，至少創建35個
        assert stats['online_bots'] >= 25  # 至少25個在線
        assert len(dynamic_operations) >= 15  # 至少15個動態操作
        assert resource_report['memory_increase_mb'] < 200  # 記憶體增長控制在200MB內
        
        print(f"持續負載測試結果:")
        print(f"  創建: {stats['total_bots']} 個 (失敗: {creation_failures})")
        print(f"  在線: {stats['online_bots']} 個")
        print(f"  動態操作: {len(dynamic_operations)} 次")
        print(f"  記憶體增長: {resource_report['memory_increase_mb']:.2f}MB")
        print(f"  平均CPU: {resource_report['average_cpu_percent']:.2f}%")
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, load_test_subbot_service, resource_monitor):
        """測試記憶體洩漏檢測"""
        service = load_test_subbot_service
        
        # 強制垃圾回收
        gc.collect()
        
        resource_monitor.start_monitoring()
        initial_memory = resource_monitor._get_memory_usage()
        
        # 循環創建和刪除子機器人，檢測記憶體洩漏
        memory_measurements = []
        
        for cycle in range(5):
            cycle_bot_ids = []
            
            # 創建一批子機器人
            for i in range(10):
                try:
                    bot_id = await service.create_sub_bot(
                        name=f"MemoryTestBot{cycle}_{i}",
                        token=f"memory_token_{cycle}_{i}",
                        target_channels=[123456789 + i]
                    )
                    cycle_bot_ids.append(bot_id)
                    await service.start_sub_bot(bot_id)
                except Exception:
                    continue
            
            # 記錄記憶體使用
            current_memory = resource_monitor._get_memory_usage()
            memory_measurements.append(current_memory)
            
            # 刪除所有子機器人
            for bot_id in cycle_bot_ids:
                try:
                    await service.delete_sub_bot(bot_id)
                except Exception:
                    continue
            
            # 強制垃圾回收
            gc.collect()
            await asyncio.sleep(0.5)  # 給系統時間清理
        
        await resource_monitor.stop_monitoring()
        
        # 分析記憶體趨勢
        final_memory = resource_monitor._get_memory_usage()
        memory_growth = final_memory - initial_memory
        
        # 檢查記憶體洩漏
        assert memory_growth < 50  # 記憶體增長不應超過50MB
        
        # 檢查記憶體使用趨勢（不應該持續上升）
        if len(memory_measurements) >= 3:
            # 比較最後三次測量的平均值與前三次的平均值
            early_avg = sum(memory_measurements[:3]) / 3
            late_avg = sum(memory_measurements[-3:]) / 3
            trend_growth = late_avg - early_avg
            
            assert trend_growth < 30  # 趨勢增長不應超過30MB
        
        print(f"記憶體洩漏測試結果:")
        print(f"  初始記憶體: {initial_memory:.2f}MB")
        print(f"  最終記憶體: {final_memory:.2f}MB")
        print(f"  總增長: {memory_growth:.2f}MB")
        print(f"  記憶體測量點: {memory_measurements}")


class TestChannelManagementLoad:
    """頻道管理負載測試"""
    
    @pytest.mark.asyncio
    async def test_concurrent_channel_assignments(self, load_test_subbot_service, load_test_channel_service, resource_monitor):
        """測試並發頻道分配"""
        bot_service = load_test_subbot_service
        channel_service = load_test_channel_service
        
        # 創建多個子機器人
        bot_ids = []
        for i in range(20):
            bot_id = await bot_service.create_sub_bot(
                name=f"ChannelBot{i}",
                token=f"channel_token_{i}",
                target_channels=[]  # 先不分配頻道
            )
            bot_ids.append(bot_id)
        
        resource_monitor.start_monitoring()
        
        # 並發分配頻道
        async def assign_channels_to_bot(bot_id, base_channel):
            channels = [base_channel + i for i in range(3)]  # 每個bot分配3個頻道
            try:
                return await channel_service.assign_channels(bot_id, channels)
            except Exception as e:
                return False
        
        assignment_tasks = [
            assign_channels_to_bot(bot_ids[i], 123456789 + i * 100)
            for i in range(20)
        ]
        
        start_time = time.time()
        assignment_results = await asyncio.gather(*assignment_tasks, return_exceptions=True)
        assignment_time = time.time() - start_time
        
        await resource_monitor.stop_monitoring()
        
        # 分析結果
        successful_assignments = [r for r in assignment_results if r is True]
        
        assert len(successful_assignments) >= 18  # 至少90%成功率
        assert assignment_time < 2.0  # 分配時間應該在2秒內
        assert len(channel_service.channel_assignments) >= 18
        
        # 檢查頻道衝突檢測
        total_channels = sum(len(channels) for channels in channel_service.channel_assignments.values())
        assert total_channels >= 54  # 18個bot * 3個頻道
        
        print(f"頻道分配測試結果:")
        print(f"  成功分配: {len(successful_assignments)} / 20")
        print(f"  分配耗時: {assignment_time:.2f}秒")
        print(f"  總頻道數: {total_channels}")
        print(f"  衝突映射: {len(channel_service.channel_conflicts)} 個唯一頻道")
    
    @pytest.mark.asyncio
    async def test_channel_conflict_resolution_load(self, load_test_subbot_service, load_test_channel_service):
        """測試頻道衝突解決負載"""
        bot_service = load_test_subbot_service
        channel_service = load_test_channel_service
        
        # 創建多個子機器人
        bot_ids = []
        for i in range(15):
            bot_id = await bot_service.create_sub_bot(
                name=f"ConflictBot{i}",
                token=f"conflict_token_{i}",
                target_channels=[]
            )
            bot_ids.append(bot_id)
        
        # 故意創建頻道衝突
        conflicts_created = 0
        shared_channels = [123456789, 987654321, 555666777]  # 共享頻道
        
        for i, bot_id in enumerate(bot_ids):
            # 前5個bot分配相同的頻道（創造衝突）
            if i < 5:
                channels = shared_channels
            else:
                channels = [123456789 + i * 10 + j for j in range(2)]
            
            try:
                await channel_service.assign_channels(bot_id, channels)
                if i < 5:
                    conflicts_created += 1
            except Exception:
                continue
        
        # 檢查衝突情況
        conflict_counts = {}
        for channel_id, assigned_bots in channel_service.channel_conflicts.items():
            if len(assigned_bots) > 1:
                conflict_counts[channel_id] = len(assigned_bots)
        
        # 驗證衝突檢測
        assert len(conflict_counts) >= 1  # 至少有一個頻道有衝突
        assert conflicts_created >= 3     # 至少創建了3個衝突的bot
        
        # 檢查共享頻道的衝突
        for shared_channel in shared_channels:
            if shared_channel in channel_service.channel_conflicts:
                assert len(channel_service.channel_conflicts[shared_channel]) >= 3
        
        print(f"頻道衝突測試結果:")
        print(f"  創建衝突bot: {conflicts_created}")
        print(f"  有衝突的頻道: {len(conflict_counts)}")
        print(f"  衝突詳情: {conflict_counts}")


class TestFailureRecoveryUnderLoad:
    """負載下的故障恢復測試"""
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, load_test_subbot_service, resource_monitor):
        """測試部分故障下的恢復能力"""
        service = load_test_subbot_service
        service.failure_rate = 0.3  # 提高失敗率到30%
        
        resource_monitor.start_monitoring()
        
        # 嘗試創建大量子機器人，預期會有失敗
        creation_attempts = 30
        successful_creates = []
        failed_creates = []
        
        for i in range(creation_attempts):
            try:
                bot_id = await service.create_sub_bot(
                    name=f"RecoveryBot{i}",
                    token=f"recovery_token_{i}",
                    target_channels=[123456789 + i % 5]
                )
                successful_creates.append(bot_id)
            except Exception as e:
                failed_creates.append(str(e))
                continue
        
        # 嘗試啟動成功創建的子機器人
        successful_starts = []
        failed_starts = []
        
        for bot_id in successful_creates:
            try:
                success = await service.start_sub_bot(bot_id)
                if success:
                    successful_starts.append(bot_id)
            except Exception as e:
                failed_starts.append(str(e))
                continue
        
        await resource_monitor.stop_monitoring()
        
        # 計算恢復率
        creation_success_rate = len(successful_creates) / creation_attempts
        start_success_rate = len(successful_starts) / len(successful_creates) if successful_creates else 0
        
        # 驗證恢復能力
        assert creation_success_rate >= 0.6   # 至少60%的創建成功率
        assert start_success_rate >= 0.6      # 至少60%的啟動成功率
        assert len(successful_starts) >= 10   # 至少10個成功啟動
        
        stats = service.get_stats()
        resource_report = resource_monitor.get_report()
        
        print(f"故障恢復測試結果:")
        print(f"  創建成功率: {creation_success_rate:.2%} ({len(successful_creates)}/{creation_attempts})")
        print(f"  啟動成功率: {start_success_rate:.2%} ({len(successful_starts)}/{len(successful_creates)})")
        print(f"  最終在線: {stats['online_bots']} 個")
        print(f"  記憶體增長: {resource_report['memory_increase_mb']:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_cascading_failure_resilience(self, load_test_subbot_service):
        """測試級聯故障復原力"""
        service = load_test_subbot_service
        
        # 創建一組子機器人
        bot_ids = []
        for i in range(10):
            bot_id = await service.create_sub_bot(
                name=f"CascadeBot{i}",
                token=f"cascade_token_{i}",
                target_channels=[123456789 + i]
            )
            bot_ids.append(bot_id)
            await service.start_sub_bot(bot_id)
        
        initial_stats = service.get_stats()
        assert initial_stats['online_bots'] >= 8  # 至少8個在線
        
        # 模擬級聯故障：高失敗率環境下的批量操作
        service.failure_rate = 0.5  # 提高失敗率到50%
        
        # 嘗試重啟所有子機器人
        recovery_successful = []
        recovery_failed = []
        
        for bot_id in bot_ids[:8]:  # 只處理前8個
            try:
                # 先停止
                await service.stop_sub_bot(bot_id)
                await asyncio.sleep(0.1)
                
                # 再啟動
                success = await service.start_sub_bot(bot_id)
                if success:
                    recovery_successful.append(bot_id)
                else:
                    recovery_failed.append(bot_id)
                    
            except Exception:
                recovery_failed.append(bot_id)
                continue
        
        final_stats = service.get_stats()
        recovery_rate = len(recovery_successful) / len(bot_ids[:8])
        
        # 驗證復原力
        assert recovery_rate >= 0.4  # 至少40%的恢復率
        assert final_stats['online_bots'] >= 4  # 至少4個仍在線
        assert len(recovery_successful) >= 3  # 至少3個成功恢復
        
        print(f"級聯故障測試結果:")
        print(f"  初始在線: {initial_stats['online_bots']}")
        print(f"  恢復成功: {len(recovery_successful)}")
        print(f"  恢復失敗: {len(recovery_failed)}")
        print(f"  最終在線: {final_stats['online_bots']}")
        print(f"  恢復率: {recovery_rate:.2%}")


class TestStressAndEdgeCases:
    """壓力和邊界條件測試"""
    
    @pytest.mark.asyncio
    async def test_rapid_creation_deletion_cycles(self, load_test_subbot_service, resource_monitor):
        """測試快速創建刪除循環"""
        service = load_test_subbot_service
        
        resource_monitor.start_monitoring()
        
        # 執行多個快速創建-刪除循環
        total_operations = 0
        successful_operations = 0
        
        for cycle in range(5):
            cycle_bots = []
            
            # 快速創建
            for i in range(8):
                try:
                    bot_id = await service.create_sub_bot(
                        name=f"RapidBot{cycle}_{i}",
                        token=f"rapid_token_{cycle}_{i}",
                        target_channels=[123456789 + i]
                    )
                    cycle_bots.append(bot_id)
                    await service.start_sub_bot(bot_id)
                    successful_operations += 1
                except Exception:
                    continue
                finally:
                    total_operations += 1
            
            await asyncio.sleep(0.2)  # 短暫運行
            
            # 快速刪除
            for bot_id in cycle_bots:
                try:
                    await service.delete_sub_bot(bot_id)
                    successful_operations += 1
                except Exception:
                    continue
                finally:
                    total_operations += 1
        
        await resource_monitor.stop_monitoring()
        
        success_rate = successful_operations / total_operations if total_operations > 0 else 0
        final_stats = service.get_stats()
        resource_report = resource_monitor.get_report()
        
        # 驗證快速操作能力
        assert success_rate >= 0.7  # 至少70%成功率
        assert final_stats['total_bots'] <= 5  # 大部分應該被刪除
        assert resource_report['memory_increase_mb'] < 100  # 記憶體增長控制
        
        print(f"快速循環測試結果:")
        print(f"  總操作: {total_operations}")
        print(f"  成功率: {success_rate:.2%}")
        print(f"  剩餘bot: {final_stats['total_bots']}")
        print(f"  記憶體增長: {resource_report['memory_increase_mb']:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_extreme_concurrency_stress(self, load_test_subbot_service, resource_monitor):
        """測試極限併發壓力"""
        service = load_test_subbot_service
        service.max_bots = 100
        
        resource_monitor.start_monitoring()
        
        # 極限併發測試：同時執行多種操作
        async def mixed_operations(worker_id):
            operations = []
            
            # 創建
            try:
                bot_id = await service.create_sub_bot(
                    name=f"StressBot{worker_id}",
                    token=f"stress_token_{worker_id}",
                    target_channels=[123456789 + worker_id % 10]
                )
                operations.append(f"created_{bot_id}")
                
                # 啟動
                await service.start_sub_bot(bot_id)
                operations.append(f"started_{bot_id}")
                
                # 短暫運行
                await asyncio.sleep(0.1)
                
                # 停止
                await service.stop_sub_bot(bot_id)
                operations.append(f"stopped_{bot_id}")
                
            except Exception as e:
                operations.append(f"error_{str(e)}")
            
            return operations
        
        # 啟動50個並發worker
        start_time = time.time()
        tasks = [mixed_operations(i) for i in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        await resource_monitor.stop_monitoring()
        
        # 分析結果
        total_operations = 0
        successful_operations = 0
        error_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                continue
            
            for operation in result:
                total_operations += 1
                if not operation.startswith('error_'):
                    successful_operations += 1
                else:
                    error_count += 1
        
        success_rate = successful_operations / total_operations if total_operations > 0 else 0
        final_stats = service.get_stats()
        resource_report = resource_monitor.get_report()
        
        # 驗證極限併發處理能力
        assert success_rate >= 0.6  # 至少60%成功率
        assert total_time < 10.0    # 總時間應該在10秒內
        assert error_count < total_operations * 0.5  # 錯誤不應超過50%
        
        print(f"極限併發測試結果:")
        print(f"  併發worker: 50")
        print(f"  總操作: {total_operations}")
        print(f"  成功率: {success_rate:.2%}")
        print(f"  錯誤數: {error_count}")
        print(f"  總耗時: {total_time:.2f}秒")
        print(f"  最終bot數: {final_stats['total_bots']}")
        print(f"  峰值記憶體: {resource_report['peak_memory_mb']:.2f}MB")
        print(f"  峰值CPU: {resource_report['peak_cpu_percent']:.2f}%")


if __name__ == "__main__":
    # 運行測試時的配置
    pytest.main([
        __file__,
        "-v",  # 詳細輸出
        "--tb=short",  # 簡短的錯誤追蹤
        "-s",  # 不捕獲輸出，顯示print
        "--asyncio-mode=auto",  # 自動asyncio模式
    ])