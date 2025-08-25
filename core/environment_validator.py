#!/usr/bin/env python3
"""
環境檢查和驗證系統
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組負責驗證部署前的環境條件和配置正確性，確保所有必要的依賴和設定都已就位。
"""

import asyncio
import datetime
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import yaml
import psutil

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """驗證結果數據類別"""
    name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None


@dataclass
class EnvironmentReport:
    """環境檢查報告"""
    timestamp: str
    system_info: Dict[str, str]
    validation_results: List[ValidationResult]
    overall_status: bool
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]


class EnvironmentValidator:
    """環境檢查器 - 驗證部署前環境條件和配置正確性"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.validation_results: List[ValidationResult] = []
        
    async def validate_environment(self) -> Tuple[bool, List[str]]:
        """
        完整環境驗證
        
        Returns:
            Tuple[bool, List[str]]: (是否通過驗證, 錯誤訊息列表)
        """
        self.logger.info("開始環境驗證檢查")
        self.validation_results = []
        
        # 系統基礎檢查
        await self._check_system_requirements()
        
        # Docker環境檢查
        await self._check_docker_environment()
        
        # 專案配置檢查
        await self._check_project_configuration()
        
        # 環境變數檢查
        await self._check_environment_variables()
        
        # 網路和端口檢查
        await self._check_network_requirements()
        
        # 磁盤空間和權限檢查
        await self._check_storage_requirements()
        
        # 彙總結果
        passed_count = sum(1 for r in self.validation_results if r.passed)
        total_count = len(self.validation_results)
        
        errors = [r.message for r in self.validation_results if not r.passed]
        overall_passed = len(errors) == 0
        
        self.logger.info(f"環境驗證完成: {passed_count}/{total_count} 項目通過")
        
        return overall_passed, errors
    
    async def _check_system_requirements(self) -> None:
        """檢查系統基本需求"""
        self.logger.debug("檢查系統基本需求")
        
        # 檢查作業系統
        os_name = platform.system()
        if os_name in ['Linux', 'Darwin']:  # Darwin = macOS
            self.validation_results.append(ValidationResult(
                name="作業系統支援",
                passed=True,
                message=f"作業系統 {os_name} 受支援",
                details={"os": os_name, "version": platform.release()}
            ))
        else:
            self.validation_results.append(ValidationResult(
                name="作業系統支援",
                passed=False,
                message=f"不支援的作業系統: {os_name}",
                suggestions=["請使用Linux或macOS系統"]
            ))
        
        # 檢查Python版本
        python_version = sys.version_info
        if python_version >= (3, 9):
            self.validation_results.append(ValidationResult(
                name="Python版本",
                passed=True,
                message=f"Python {python_version.major}.{python_version.minor} 符合需求",
                details={"version": f"{python_version.major}.{python_version.minor}.{python_version.micro}"}
            ))
        else:
            self.validation_results.append(ValidationResult(
                name="Python版本",
                passed=False,
                message=f"Python版本過舊: {python_version.major}.{python_version.minor}",
                suggestions=["請升級到Python 3.9或更高版本"]
            ))
        
        # 檢查記憶體
        memory = psutil.virtual_memory()
        memory_gb = memory.total / (1024 ** 3)
        if memory_gb >= 2.0:
            self.validation_results.append(ValidationResult(
                name="系統記憶體",
                passed=True,
                message=f"可用記憶體: {memory_gb:.1f}GB",
                details={"total_gb": round(memory_gb, 1), "available_gb": round(memory.available / (1024 ** 3), 1)}
            ))
        else:
            self.validation_results.append(ValidationResult(
                name="系統記憶體",
                passed=False,
                message=f"記憶體不足: {memory_gb:.1f}GB",
                suggestions=["建議至少2GB記憶體"]
            ))
    
    async def _check_docker_environment(self) -> None:
        """檢查Docker環境"""
        self.logger.debug("檢查Docker環境")
        
        # 檢查Docker是否安裝
        docker_installed = shutil.which('docker') is not None
        if not docker_installed:
            self.validation_results.append(ValidationResult(
                name="Docker安裝",
                passed=False,
                message="Docker未安裝",
                suggestions=["請安裝Docker Engine"]
            ))
            return
        
        # 檢查Docker版本
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                docker_version = result.stdout.strip()
                self.validation_results.append(ValidationResult(
                    name="Docker版本",
                    passed=True,
                    message=f"Docker已安裝: {docker_version}",
                    details={"version_output": docker_version}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    name="Docker版本",
                    passed=False,
                    message="無法獲取Docker版本",
                    suggestions=["檢查Docker安裝是否正確"]
                ))
        except subprocess.TimeoutExpired:
            self.validation_results.append(ValidationResult(
                name="Docker版本",
                passed=False,
                message="Docker命令執行超時",
                suggestions=["檢查Docker daemon是否正在運行"]
            ))
        except Exception as e:
            self.validation_results.append(ValidationResult(
                name="Docker版本",
                passed=False,
                message=f"Docker版本檢查失敗: {str(e)}",
                suggestions=["檢查Docker安裝和權限"]
            ))
        
        # 檢查Docker Compose
        await self._check_docker_compose()
        
        # 檢查Docker服務狀態
        await self._check_docker_service()
    
    async def _check_docker_compose(self) -> None:
        """檢查Docker Compose"""
        # 優先檢查新版本的docker compose命令
        compose_v2_available = False
        try:
            result = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                compose_version = result.stdout.strip()
                self.validation_results.append(ValidationResult(
                    name="Docker Compose V2",
                    passed=True,
                    message=f"Docker Compose V2可用: {compose_version}",
                    details={"version_output": compose_version}
                ))
                compose_v2_available = True
        except Exception:
            pass
        
        # 如果V2不可用，檢查舊版本
        if not compose_v2_available:
            compose_installed = shutil.which('docker-compose') is not None
            if compose_installed:
                try:
                    result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        compose_version = result.stdout.strip()
                        self.validation_results.append(ValidationResult(
                            name="Docker Compose V1",
                            passed=True,
                            message=f"Docker Compose V1可用: {compose_version}",
                            details={"version_output": compose_version},
                            suggestions=["建議升級到Docker Compose V2"]
                        ))
                except Exception as e:
                    self.validation_results.append(ValidationResult(
                        name="Docker Compose",
                        passed=False,
                        message=f"Docker Compose檢查失敗: {str(e)}",
                        suggestions=["檢查Docker Compose安裝"]
                    ))
            else:
                self.validation_results.append(ValidationResult(
                    name="Docker Compose",
                    passed=False,
                    message="Docker Compose未安裝",
                    suggestions=["請安裝Docker Compose"]
                ))
    
    async def _check_docker_service(self) -> None:
        """檢查Docker服務狀態"""
        try:
            # 檢查Docker daemon是否運行
            result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                self.validation_results.append(ValidationResult(
                    name="Docker服務",
                    passed=True,
                    message="Docker daemon正在運行",
                    details={"docker_info_available": True}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    name="Docker服務",
                    passed=False,
                    message="Docker daemon未運行",
                    suggestions=["啟動Docker daemon"]
                ))
        except subprocess.TimeoutExpired:
            self.validation_results.append(ValidationResult(
                name="Docker服務",
                passed=False,
                message="Docker服務檢查超時",
                suggestions=["檢查Docker daemon狀態"]
            ))
        except Exception as e:
            self.validation_results.append(ValidationResult(
                name="Docker服務",
                passed=False,
                message=f"Docker服務檢查失敗: {str(e)}",
                suggestions=["檢查Docker服務和權限"]
            ))
    
    async def _check_project_configuration(self) -> None:
        """檢查專案配置檔案"""
        self.logger.debug("檢查專案配置檔案")
        
        # 檢查必要的配置檔案
        required_files = [
            'pyproject.toml',
            'Dockerfile',
            'docker-compose.dev.yml',
            'docker-compose.prod.yml'
        ]
        
        for filename in required_files:
            file_path = self.project_root / filename
            if file_path.exists():
                self.validation_results.append(ValidationResult(
                    name=f"配置檔案: {filename}",
                    passed=True,
                    message=f"{filename} 存在",
                    details={"path": str(file_path)}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    name=f"配置檔案: {filename}",
                    passed=False,
                    message=f"缺少必要檔案: {filename}",
                    suggestions=[f"請確保專案根目錄包含 {filename}"]
                ))
        
        # 驗證Docker Compose檔案格式
        await self._validate_compose_files()
    
    async def _validate_compose_files(self) -> None:
        """驗證Docker Compose檔案格式"""
        compose_files = ['docker-compose.dev.yml', 'docker-compose.prod.yml']
        
        for compose_file in compose_files:
            file_path = self.project_root / compose_file
            if not file_path.exists():
                continue
            
            try:
                # 使用docker compose config驗證語法
                env = os.environ.copy()
                env['DISCORD_TOKEN'] = env.get('DISCORD_TOKEN', 'dummy_token_for_validation')
                
                result = subprocess.run(
                    ['docker', 'compose', '-f', str(file_path), 'config'],
                    capture_output=True, text=True, timeout=30, env=env
                )
                
                if result.returncode == 0:
                    self.validation_results.append(ValidationResult(
                        name=f"Compose語法: {compose_file}",
                        passed=True,
                        message=f"{compose_file} 語法正確"
                    ))
                else:
                    self.validation_results.append(ValidationResult(
                        name=f"Compose語法: {compose_file}",
                        passed=False,
                        message=f"{compose_file} 語法錯誤: {result.stderr}",
                        suggestions=["修正Docker Compose配置語法錯誤"]
                    ))
            except subprocess.TimeoutExpired:
                self.validation_results.append(ValidationResult(
                    name=f"Compose語法: {compose_file}",
                    passed=False,
                    message=f"{compose_file} 驗證超時",
                    suggestions=["檢查Compose配置複雜度"]
                ))
            except Exception as e:
                self.validation_results.append(ValidationResult(
                    name=f"Compose語法: {compose_file}",
                    passed=False,
                    message=f"{compose_file} 驗證失敗: {str(e)}",
                    suggestions=["檢查Docker Compose安裝和文件權限"]
                ))
    
    async def _check_environment_variables(self) -> None:
        """檢查必要的環境變數"""
        self.logger.debug("檢查環境變數")
        
        required_vars = {
            'DISCORD_TOKEN': '必要的Discord機器人Token',
        }
        
        optional_vars = {
            'ENVIRONMENT': '執行環境 (development/production)',
            'DEBUG': '偵錯模式開關',
            'LOG_LEVEL': '日誌級別設定'
        }
        
        # 檢查必要變數
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if value:
                # 不記錄敏感資訊的實際值
                self.validation_results.append(ValidationResult(
                    name=f"環境變數: {var_name}",
                    passed=True,
                    message=f"{var_name} 已設定",
                    details={"description": description, "has_value": True}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    name=f"環境變數: {var_name}",
                    passed=False,
                    message=f"缺少必要環境變數: {var_name}",
                    suggestions=[f"請設定 {var_name}: {description}"]
                ))
        
        # 檢查可選變數
        for var_name, description in optional_vars.items():
            value = os.getenv(var_name)
            if value:
                self.validation_results.append(ValidationResult(
                    name=f"可選變數: {var_name}",
                    passed=True,
                    message=f"{var_name} = {value}",
                    details={"description": description}
                ))
    
    async def _check_network_requirements(self) -> None:
        """檢查網路和端口需求"""
        self.logger.debug("檢查網路需求")
        
        # 檢查重要端口是否被佔用
        important_ports = [6379, 8000, 3000, 9090]  # Redis, App, Grafana, Prometheus
        
        for port in important_ports:
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    result = s.connect_ex(('localhost', port))
                    if result == 0:
                        self.validation_results.append(ValidationResult(
                            name=f"端口檢查: {port}",
                            passed=False,
                            message=f"端口 {port} 已被佔用",
                            suggestions=[f"請關閉佔用端口 {port} 的程序"]
                        ))
                    else:
                        self.validation_results.append(ValidationResult(
                            name=f"端口檢查: {port}",
                            passed=True,
                            message=f"端口 {port} 可用"
                        ))
            except Exception as e:
                self.validation_results.append(ValidationResult(
                    name=f"端口檢查: {port}",
                    passed=False,
                    message=f"端口 {port} 檢查失敗: {str(e)}",
                    suggestions=["檢查網路配置"]
                ))
    
    async def _check_storage_requirements(self) -> None:
        """檢查磁盤空間和權限"""
        self.logger.debug("檢查存儲需求")
        
        # 檢查磁盤空間
        try:
            disk_usage = psutil.disk_usage(str(self.project_root))
            free_space_gb = disk_usage.free / (1024 ** 3)
            
            if free_space_gb >= 5.0:  # 至少5GB空間
                self.validation_results.append(ValidationResult(
                    name="磁盤空間",
                    passed=True,
                    message=f"可用空間: {free_space_gb:.1f}GB",
                    details={"free_space_gb": round(free_space_gb, 1)}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    name="磁盤空間",
                    passed=False,
                    message=f"磁盤空間不足: {free_space_gb:.1f}GB",
                    suggestions=["建議至少有5GB可用空間"]
                ))
        except Exception as e:
            self.validation_results.append(ValidationResult(
                name="磁盤空間",
                passed=False,
                message=f"磁盤空間檢查失敗: {str(e)}"
            ))
        
        # 檢查目錄權限
        required_dirs = ['data', 'logs', 'backups']
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            try:
                # 確保目錄存在
                dir_path.mkdir(exist_ok=True)
                
                # 測試寫入權限
                test_file = dir_path / '.write_test'
                test_file.write_text('test')
                test_file.unlink()  # 清理測試文件
                
                self.validation_results.append(ValidationResult(
                    name=f"目錄權限: {dir_name}",
                    passed=True,
                    message=f"{dir_name} 目錄權限正常",
                    details={"path": str(dir_path)}
                ))
            except Exception as e:
                self.validation_results.append(ValidationResult(
                    name=f"目錄權限: {dir_name}",
                    passed=False,
                    message=f"{dir_name} 目錄權限問題: {str(e)}",
                    suggestions=[f"檢查 {dir_path} 的讀寫權限"]
                ))
    
    def generate_report(self) -> EnvironmentReport:
        """生成環境檢查報告"""
        system_info = {
            "os": platform.system(),
            "version": platform.release(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "architecture": platform.machine()
        }
        
        critical_issues = [r.message for r in self.validation_results if not r.passed]
        warnings = []
        recommendations = []
        
        for result in self.validation_results:
            if result.suggestions:
                recommendations.extend(result.suggestions)
        
        overall_status = len(critical_issues) == 0
        
        return EnvironmentReport(
            timestamp=datetime.datetime.now().isoformat(),
            system_info=system_info,
            validation_results=self.validation_results,
            overall_status=overall_status,
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations
        )
    
    def save_report(self, report: EnvironmentReport, output_path: Optional[Path] = None) -> Path:
        """保存檢查報告到文件"""
        if output_path is None:
            output_path = self.project_root / f"environment-validation-{int(datetime.datetime.now().timestamp())}.json"
        
        report_data = asdict(report)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"環境檢查報告已保存: {output_path}")
        return output_path


async def main():
    """主函數 - 用於獨立執行環境檢查"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 環境檢查工具')
    parser.add_argument('--project-root', type=Path, help='專案根目錄')
    parser.add_argument('--output', type=Path, help='報告輸出路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 執行環境檢查
    validator = EnvironmentValidator(args.project_root)
    passed, errors = await validator.validate_environment()
    
    # 生成報告
    report = validator.generate_report()
    output_path = validator.save_report(report, args.output)
    
    # 輸出結果
    print(f"\n{'='*60}")
    print("🔍 ROAS Bot v2.4.3 環境檢查報告")
    print(f"{'='*60}")
    print(f"檢查時間: {report.timestamp}")
    print(f"系統資訊: {report.system_info['os']} {report.system_info['version']}")
    print(f"Python版本: {report.system_info['python_version']}")
    print(f"\n總體狀態: {'✅ 通過' if passed else '❌ 失敗'}")
    print(f"檢查項目: {len(report.validation_results)}")
    print(f"關鍵問題: {len(report.critical_issues)}")
    
    if report.critical_issues:
        print(f"\n❌ 關鍵問題:")
        for issue in report.critical_issues:
            print(f"  • {issue}")
    
    if report.recommendations:
        print(f"\n💡 建議:")
        for rec in set(report.recommendations):  # 去重
            print(f"  • {rec}")
    
    print(f"\n📄 詳細報告: {output_path}")
    
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))