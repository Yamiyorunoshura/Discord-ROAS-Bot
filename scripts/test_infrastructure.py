#!/usr/bin/env python3
"""
基礎設施模組整合測試腳本
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

快速驗證所有基礎設施模組是否正常工作
"""

import asyncio
import tempfile
import os
from pathlib import Path

# 導入我們的基礎設施模組
from core.environment_validator import EnvironmentValidator
from core.deployment_manager import DeploymentManager, create_deployment_manager
from core.monitoring_collector import MonitoringCollector, quick_health_check
from core.error_handler import ErrorHandler


async def test_environment_validator():
    """測試環境驗證器"""
    print("🔍 測試環境驗證器...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        
        # 創建基本檔案
        (project_path / 'pyproject.toml').write_text('[tool.poetry]\nname = "test"')
        (project_path / 'Dockerfile').write_text('FROM python:3.9\nWORKDIR /app')
        (project_path / 'docker-compose.dev.yml').write_text('''
services:
  test:
    image: test:latest
''')
        
        validator = EnvironmentValidator(project_path)
        
        # 設置測試環境變數
        os.environ['DISCORD_TOKEN'] = 'test_token_for_validation'
        
        try:
            passed, errors = await validator.validate_environment()
            report = validator.generate_report()
            
            print(f"   ✅ 驗證結果: {len(validator.validation_results)} 個檢查項目")
            print(f"   ✅ 整體狀態: {'通過' if report.overall_status else '有問題'}")
            print(f"   ✅ 關鍵問題: {len(report.critical_issues)} 個")
            
            return True
        except Exception as e:
            print(f"   ❌ 環境驗證器測試失敗: {str(e)}")
            return False
        finally:
            if 'DISCORD_TOKEN' in os.environ:
                del os.environ['DISCORD_TOKEN']


async def test_deployment_manager():
    """測試部署管理器"""
    print("🚀 測試部署管理器...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        
        # 創建docker-compose文件
        compose_content = '''
services:
  test-service:
    image: alpine:latest
    command: sleep 10
'''
        (project_path / 'docker-compose.test.yml').write_text(compose_content)
        
        try:
            # 測試初始化
            manager = DeploymentManager(project_path, 'docker-compose.test.yml')
            print(f"   ✅ 部署管理器初始化成功")
            
            # 測試工廠方法
            dev_manager = create_deployment_manager('dev')
            prod_manager = create_deployment_manager('prod')
            print(f"   ✅ 工廠方法: dev={dev_manager.compose_file}, prod={prod_manager.compose_file}")
            
            # 測試基本功能（不實際執行Docker命令）
            compose_cmd = manager._get_compose_command()
            print(f"   ✅ Compose命令: {' '.join(compose_cmd)}")
            
            return True
        except Exception as e:
            print(f"   ❌ 部署管理器測試失敗: {str(e)}")
            return False


async def test_monitoring_collector():
    """測試監控收集器"""
    print("📊 測試監控收集器...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        (project_path / 'data').mkdir(exist_ok=True)
        
        try:
            collector = MonitoringCollector(project_path)
            print(f"   ✅ 監控收集器初始化成功")
            
            # 測試系統指標收集
            system_metrics = await collector._collect_system_metrics()
            print(f"   ✅ 系統指標: CPU={system_metrics.cpu_usage_percent:.1f}%, "
                  f"記憶體={system_metrics.memory_usage_percent:.1f}%")
            
            # 檢查資料庫是否創建
            db_path = project_path / 'data' / 'monitoring.db'
            if db_path.exists():
                print(f"   ✅ 監控資料庫已創建: {db_path}")
            
            return True
        except Exception as e:
            print(f"   ❌ 監控收集器測試失敗: {str(e)}")
            return False


async def test_error_handler():
    """測試錯誤處理器"""
    print("🔧 測試錯誤處理器...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        (project_path / 'data').mkdir(exist_ok=True)
        
        try:
            handler = ErrorHandler(project_path)
            print(f"   ✅ 錯誤處理器初始化成功")
            
            # 測試錯誤分類
            docker_error = Exception("docker: command not found")
            category, severity = handler._classify_error(docker_error, {'operation': 'deploy'})
            print(f"   ✅ 錯誤分類: {category.value}, 嚴重性: {severity.value}")
            
            # 測試錯誤處理流程
            test_error = Exception("測試錯誤")
            context = {'test': True, 'operation': 'integration_test'}
            recovery_action = await handler.handle_error(test_error, context)
            print(f"   ✅ 恢復動作: {recovery_action.action_type}")
            
            # 檢查資料庫是否創建
            db_path = project_path / 'data' / 'errors.db'
            if db_path.exists():
                print(f"   ✅ 錯誤資料庫已創建: {db_path}")
            
            return True
        except Exception as e:
            print(f"   ❌ 錯誤處理器測試失敗: {str(e)}")
            return False


async def test_docker_compose_validation():
    """測試Docker Compose配置驗證"""
    print("🐳 測試Docker Compose配置...")
    
    try:
        # 驗證開發環境配置
        result = os.system('DISCORD_TOKEN=test docker-compose -f docker-compose.dev.yml config --quiet')
        if result == 0:
            print("   ✅ 開發環境Docker Compose配置有效")
        else:
            print("   ❌ 開發環境Docker Compose配置無效")
            return False
        
        # 驗證生產環境配置
        result = os.system('DISCORD_TOKEN=test docker-compose -f docker-compose.prod.yml config --quiet')
        if result == 0:
            print("   ✅ 生產環境Docker Compose配置有效")
        else:
            print("   ❌ 生產環境Docker Compose配置無效")
            return False
        
        return True
    except Exception as e:
        print(f"   ❌ Docker Compose驗證失敗: {str(e)}")
        return False


async def main():
    """主測試函數"""
    print("🎯 開始基礎設施模組整合測試")
    print("="*60)
    
    test_results = []
    
    # 執行各項測試
    test_results.append(await test_environment_validator())
    test_results.append(await test_deployment_manager())
    test_results.append(await test_monitoring_collector())
    test_results.append(await test_error_handler())
    test_results.append(await test_docker_compose_validation())
    
    # 統計結果
    passed = sum(test_results)
    total = len(test_results)
    
    print("="*60)
    print(f"🎯 測試完成: {passed}/{total} 項測試通過")
    
    if passed == total:
        print("✅ 所有基礎設施模組測試通過！")
        print("\n🚀 基礎設施系統已準備就緒，可以進行部署。")
    else:
        print("❌ 部分測試失敗，請檢查上述錯誤訊息。")
    
    return passed == total


if __name__ == '__main__':
    success = asyncio.run(main())
    exit(0 if success else 1)