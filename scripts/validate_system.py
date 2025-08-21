#!/usr/bin/env python3
"""
系統驗證腳本
Task ID: 9 - 重構現有模組以符合新架構

這個腳本用來驗證所有重構後的模組是否能正確載入和初始化：
- 檢查服務啟動管理器能否正常運作
- 驗證所有服務的正確註冊和初始化
- 測試 Cogs 能否正確使用統一的服務機制
- 確認系統的整體健康狀態
"""

import asyncio
import os
import sys
import logging
from typing import Dict, Any

# 設定專案根目錄
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database_manager import get_database_manager
from core.service_startup_manager import get_startup_manager
from core.base_service import service_registry
from config import (
    SERVICE_INIT_TIMEOUT, SERVICE_CLEANUP_TIMEOUT, 
    SERVICE_BATCH_SIZE, SERVICE_HEALTH_CHECK_INTERVAL,
    FONTS_DIR, WELCOME_DEFAULT_FONT, BG_DIR
)

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemValidator:
    """系統驗證器"""
    
    def __init__(self):
        self.startup_manager = None
        self.db_manager = None
        self.validation_results = {
            "database_manager": False,
            "startup_manager": False,
            "service_discovery": False,
            "service_initialization": False,
            "service_health": False,
            "cleanup": False
        }
    
    async def run_validation(self) -> bool:
        """執行完整的系統驗證"""
        logger.info("🔍 開始系統驗證...")
        
        try:
            # 1. 驗證資料庫管理器
            await self.validate_database_manager()
            
            # 2. 驗證服務啟動管理器
            await self.validate_startup_manager()
            
            # 3. 驗證服務發現機制
            await self.validate_service_discovery()
            
            # 4. 驗證服務初始化
            await self.validate_service_initialization()
            
            # 5. 驗證服務健康狀態
            await self.validate_service_health()
            
            # 6. 驗證清理機制
            await self.validate_cleanup()
            
            # 顯示驗證結果
            self.display_validation_results()
            
            # 檢查是否全部通過
            all_passed = all(self.validation_results.values())
            if all_passed:
                logger.info("✅ 系統驗證全部通過！")
            else:
                logger.error("❌ 部分驗證項目失敗")
            
            return all_passed
            
        except Exception as e:
            logger.exception(f"❌ 系統驗證過程中發生錯誤：{e}")
            return False
    
    async def validate_database_manager(self):
        """驗證資料庫管理器"""
        logger.info("📊 驗證資料庫管理器...")
        try:
            self.db_manager = await get_database_manager()
            
            if self.db_manager and self.db_manager.is_initialized:
                logger.info("   ✅ 資料庫管理器初始化成功")
                
                # 測試基本操作
                stats = await self.db_manager.get_database_stats()
                logger.info(f"   ℹ️  資料庫統計：{len(stats.get('main_database', {}).get('tables', []))} 個主表")
                
                self.validation_results["database_manager"] = True
            else:
                logger.error("   ❌ 資料庫管理器初始化失敗")
                
        except Exception as e:
            logger.error(f"   ❌ 資料庫管理器驗證失敗：{e}")
    
    async def validate_startup_manager(self):
        """驗證服務啟動管理器"""
        logger.info("🚀 驗證服務啟動管理器...")
        try:
            startup_config = {
                'service_init_timeout': SERVICE_INIT_TIMEOUT,
                'service_cleanup_timeout': SERVICE_CLEANUP_TIMEOUT,
                'service_batch_size': SERVICE_BATCH_SIZE,
                'service_health_check_interval': SERVICE_HEALTH_CHECK_INTERVAL,
                'fonts_dir': FONTS_DIR,
                'default_font': WELCOME_DEFAULT_FONT,
                'bg_dir': BG_DIR
            }
            
            self.startup_manager = await get_startup_manager(startup_config)
            
            if self.startup_manager:
                logger.info("   ✅ 服務啟動管理器初始化成功")
                logger.info(f"   ℹ️  發現服務：{len(self.startup_manager.discovered_services)} 個")
                
                for service_name in self.startup_manager.discovered_services.keys():
                    logger.info(f"      - {service_name}")
                
                self.validation_results["startup_manager"] = True
            else:
                logger.error("   ❌ 服務啟動管理器初始化失敗")
                
        except Exception as e:
            logger.error(f"   ❌ 服務啟動管理器驗證失敗：{e}")
    
    async def validate_service_discovery(self):
        """驗證服務發現機制"""
        logger.info("🔎 驗證服務發現機制...")
        try:
            if not self.startup_manager:
                logger.error("   ❌ 服務啟動管理器未初始化")
                return
            
            expected_services = ['ActivityService', 'WelcomeService', 'MessageService']
            discovered_services = list(self.startup_manager.discovered_services.keys())
            
            found_services = []
            missing_services = []
            
            for service in expected_services:
                if service in discovered_services:
                    found_services.append(service)
                    logger.info(f"   ✅ 發現服務：{service}")
                else:
                    missing_services.append(service)
                    logger.warning(f"   ⚠️  未發現服務：{service}")
            
            if len(found_services) >= 2:  # 至少要有2個服務被發現才算通過
                self.validation_results["service_discovery"] = True
                logger.info(f"   ✅ 服務發現驗證通過（{len(found_services)}/{len(expected_services)}）")
            else:
                logger.error(f"   ❌ 服務發現驗證失敗，發現服務數量不足")
                
        except Exception as e:
            logger.error(f"   ❌ 服務發現驗證失敗：{e}")
    
    async def validate_service_initialization(self):
        """驗證服務初始化"""
        logger.info("⚙️  驗證服務初始化...")
        try:
            if not self.startup_manager:
                logger.error("   ❌ 服務啟動管理器未初始化")
                return
            
            # 初始化所有服務
            success = await self.startup_manager.initialize_all_services()
            
            if success:
                initialized_services = list(self.startup_manager.service_instances.keys())
                logger.info(f"   ✅ 服務初始化成功，共 {len(initialized_services)} 個服務")
                
                for service_name in initialized_services:
                    service = self.startup_manager.service_instances[service_name]
                    if service.is_initialized:
                        logger.info(f"      ✅ {service_name} - 已初始化")
                    else:
                        logger.warning(f"      ⚠️  {service_name} - 初始化狀態異常")
                
                if len(initialized_services) > 0:
                    self.validation_results["service_initialization"] = True
                    
                    # 顯示啟動摘要
                    startup_summary = self.startup_manager.get_startup_summary()
                    if startup_summary['elapsed_seconds']:
                        logger.info(f"   ⏱️  服務啟動耗時：{startup_summary['elapsed_seconds']:.2f} 秒")
                
            else:
                logger.error("   ❌ 服務初始化失敗")
                
        except Exception as e:
            logger.error(f"   ❌ 服務初始化驗證失敗：{e}")
    
    async def validate_service_health(self):
        """驗證服務健康狀態"""
        logger.info("💊 驗證服務健康狀態...")
        try:
            if not self.startup_manager:
                logger.error("   ❌ 服務啟動管理器未初始化")
                return
            
            health_report = await self.startup_manager.get_service_health_status()
            
            healthy_services = 0
            total_services = len(health_report.get('services', {}))
            
            for service_name, health_status in health_report.get('services', {}).items():
                status = health_status.get('status', 'unknown')
                if status == 'healthy':
                    healthy_services += 1
                    logger.info(f"   ✅ {service_name} - 健康")
                elif status == 'error':
                    error_msg = health_status.get('error', 'Unknown error')
                    logger.warning(f"   ❌ {service_name} - 錯誤：{error_msg}")
                else:
                    logger.info(f"   ℹ️  {service_name} - 狀態：{status}")
            
            if total_services > 0 and healthy_services >= total_services * 0.8:  # 80%以上健康才算通過
                self.validation_results["service_health"] = True
                logger.info(f"   ✅ 服務健康檢查通過（{healthy_services}/{total_services}）")
            else:
                logger.error(f"   ❌ 服務健康檢查失敗（{healthy_services}/{total_services}）")
                
        except Exception as e:
            logger.error(f"   ❌ 服務健康驗證失敗：{e}")
    
    async def validate_cleanup(self):
        """驗證清理機制"""
        logger.info("🧹 驗證清理機制...")
        try:
            if self.startup_manager:
                await self.startup_manager.cleanup_all_services()
                logger.info("   ✅ 服務啟動管理器清理成功")
            
            if self.db_manager:
                await self.db_manager.cleanup()
                logger.info("   ✅ 資料庫管理器清理成功")
            
            self.validation_results["cleanup"] = True
            
        except Exception as e:
            logger.error(f"   ❌ 清理驗證失敗：{e}")
    
    def display_validation_results(self):
        """顯示驗證結果"""
        logger.info("\n" + "="*60)
        logger.info("📋 系統驗證結果摘要")
        logger.info("="*60)
        
        for item, passed in self.validation_results.items():
            status = "✅ 通過" if passed else "❌ 失敗"
            item_name = item.replace("_", " ").title()
            logger.info(f"{item_name:25} {status}")
        
        passed_count = sum(self.validation_results.values())
        total_count = len(self.validation_results)
        
        logger.info("-"*60)
        logger.info(f"總計：{passed_count}/{total_count} 項驗證通過")
        
        if passed_count == total_count:
            logger.info("🎉 恭喜！系統驗證全部通過！")
        elif passed_count >= total_count * 0.8:
            logger.info("⚠️  系統基本可用，但仍有部分問題需要解決")
        else:
            logger.info("❌ 系統存在嚴重問題，需要立即修復")
        
        logger.info("="*60)

async def main():
    """主程式"""
    print("🎯 Discord ADR Bot v2.4 - 系統驗證工具")
    print("=" * 60)
    
    validator = SystemValidator()
    success = await validator.run_validation()
    
    if success:
        print("\n🎉 系統驗證完成：所有檢查項目均通過！")
        print("系統已準備就緒，可以正常啟動 Discord 機器人。")
        sys.exit(0)
    else:
        print("\n❌ 系統驗證失敗：發現問題需要修復")
        print("請查看上方的錯誤訊息並修復問題後重新驗證。")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 驗證被用戶中斷")
    except Exception as e:
        print(f"\n💥 驗證過程中發生未預期錯誤：{e}")
        sys.exit(1)