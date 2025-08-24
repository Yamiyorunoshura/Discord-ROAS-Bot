"""
Docker效能基準測試執行器 - 驗證10分鐘目標
Task ID: T1 - Docker 測試框架建立 (效能驗證)

此腳本用於驗證Docker測試套件是否能在10分鐘內完成
並且符合所有效能約束條件（記憶體≤2GB，CPU≤80%）
"""

import sys
import time
import logging
from pathlib import Path

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import docker
    from tests.docker.performance_benchmark_suite import run_docker_performance_benchmark
    DOCKER_AVAILABLE = True
except ImportError as e:
    print(f"Docker 測試不可用: {e}")
    DOCKER_AVAILABLE = False
    sys.exit(1)

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主要執行函數"""
    if not DOCKER_AVAILABLE:
        print("❌ Docker SDK 不可用，無法執行效能測試")
        return False
    
    try:
        # 連接 Docker 客戶端
        docker_client = docker.from_env()
        docker_client.ping()
        logger.info("✅ Docker 連接成功")
        
    except Exception as e:
        logger.error(f"❌ Docker 連接失敗: {e}")
        return False
    
    # 檢查測試鏡像
    test_image = "roas-bot"
    try:
        docker_client.images.get(test_image)
        logger.info(f"✅ 測試鏡像 {test_image} 存在")
    except docker.errors.ImageNotFound:
        logger.error(f"❌ 測試鏡像 {test_image} 不存在")
        return False
    
    print("🚀 開始Docker效能基準測試...")
    print("🎯 目標：10分鐘內完成所有測試，記憶體≤2GB，CPU≤80%")
    print("-" * 60)
    
    # 執行效能基準測試
    start_time = time.time()
    
    try:
        benchmark_report = run_docker_performance_benchmark(docker_client, test_image)
        execution_time = time.time() - start_time
        
        # 顯示結果摘要
        print_benchmark_summary(benchmark_report, execution_time)
        
        # 檢查是否達成目標
        success = check_performance_targets(benchmark_report, execution_time)
        
        return success
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"❌ 基準測試執行失敗: {e}")
        print(f"⏱️  執行時間: {execution_time:.2f} 秒")
        return False
    
    finally:
        # 清理 Docker 客戶端
        docker_client.close()


def print_benchmark_summary(report: dict, execution_time: float) -> None:
    """打印基準測試摘要"""
    print(f"⏱️  總執行時間: {execution_time:.2f} 秒 ({execution_time/60:.2f} 分鐘)")
    
    overall_performance = report.get('overall_performance', {})
    performance_score = overall_performance.get('overall_performance_score', 0)
    performance_grade = overall_performance.get('performance_grade', 'N/A')
    
    print(f"📊 整體效能評分: {performance_score:.1f}/100 (等級: {performance_grade})")
    
    passed_benchmarks = overall_performance.get('passed_benchmarks', 0)
    total_benchmarks = overall_performance.get('total_benchmarks', 0)
    pass_rate = overall_performance.get('pass_rate_percent', 0)
    
    print(f"✅ 基準測試通過: {passed_benchmarks}/{total_benchmarks} ({pass_rate:.1f}%)")
    
    # 合規性狀態
    compliance = report.get('compliance_status', {})
    print("\n📋 合規性檢查:")
    print(f"  ⏰ 10分鐘目標: {'✅' if compliance.get('meets_10min_target') else '❌'}")
    print(f"  🧠 2GB記憶體限制: {'✅' if compliance.get('meets_2gb_memory_limit') else '❌'}")
    print(f"  ⚡ 80% CPU限制: {'✅' if compliance.get('meets_80_percent_cpu_limit') else '❌'}")
    print(f"  🎯 98%成功率: {'✅' if compliance.get('meets_98_percent_success_rate') else '❌'}")
    
    # 優化建議
    recommendations = report.get('optimization_recommendations', [])
    if recommendations:
        print("\n💡 優化建議:")
        for i, rec in enumerate(recommendations[:3], 1):  # 只顯示前3個建議
            print(f"  {i}. {rec}")


def check_performance_targets(report: dict, execution_time: float) -> bool:
    """檢查是否達成效能目標"""
    success = True
    
    # 檢查10分鐘目標
    if execution_time > 600:  # 10分鐘
        print(f"❌ 執行時間 {execution_time:.1f}s 超過10分鐘目標")
        success = False
    else:
        print(f"✅ 執行時間 {execution_time:.1f}s 符合10分鐘目標")
    
    # 檢查合規性
    compliance = report.get('compliance_status', {})
    
    if not compliance.get('meets_2gb_memory_limit', True):
        print("❌ 記憶體使用超過2GB限制")
        success = False
    
    if not compliance.get('meets_80_percent_cpu_limit', True):
        print("❌ CPU使用超過80%限制")
        success = False
    
    if not compliance.get('meets_98_percent_success_rate', True):
        print("❌ 測試成功率低於98%目標")
        success = False
    
    # 檢查整體效能評分
    overall_performance = report.get('overall_performance', {})
    performance_score = overall_performance.get('overall_performance_score', 0)
    
    if performance_score < 85:  # B+ 等級
        print(f"⚠️  整體效能評分 {performance_score:.1f} 低於優秀標準 (85分)")
        success = False
    
    if success:
        print("🎉 所有效能目標都已達成！")
    else:
        print("⚠️  部分效能目標未達成，需要進一步優化")
    
    return success


if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🏆 Docker測試效能驗證成功！")
        print("✅ 測試套件符合所有效能要求")
        sys.exit(0)
    else:
        print("\n❌ Docker測試效能驗證失敗")
        print("⚠️  需要檢查和優化測試配置")
        sys.exit(1)