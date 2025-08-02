"""
部署文件測試模組
驗證部署相關文件和腳本的正確性
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import docker
import pytest
import yaml
from docker.errors import DockerException


class DeploymentTester:
    """部署測試器"""

    def __init__(self):
        self.project_root = Path.cwd()
        self.docs_path = self.project_root / "docs"
        self.scripts_path = self.project_root / "scripts"
        self.docker_files = [
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.prod.yml",
            ".dockerignore"
        ]

    def test_docker_files_exist(self) -> dict[str, Any]:
        """測試 Docker 相關文件是否存在"""
        results = {}

        for docker_file in self.docker_files:
            file_path = self.project_root / docker_file
            results[docker_file] = {
                "exists": file_path.exists(),
                "path": str(file_path)
            }

        return results

    def test_dockerfile_syntax(self) -> dict[str, Any]:
        """測試 Dockerfile 語法"""
        dockerfile_path = self.project_root / "Dockerfile"

        if not dockerfile_path.exists():
            return {"valid": False, "error": "Dockerfile 不存在"}

        try:
            # 使用 docker build 進行語法檢查（dry run）
            result = subprocess.run([
                "docker", "build", "--dry-run", "-f", str(dockerfile_path), "."
            ], check=False, capture_output=True, text=True, cwd=self.project_root, timeout=60)

            return {
                "valid": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {"valid": False, "error": "Dockerfile 語法檢查超時"}
        except FileNotFoundError:
            return {"valid": False, "error": "Docker 未安裝或不在 PATH 中"}
        except Exception as e:
            return {"valid": False, "error": f"Dockerfile 語法檢查失敗: {e!s}"}

    def test_docker_compose_syntax(self) -> dict[str, Any]:
        """測試 Docker Compose 文件語法"""
        results = {}

        compose_files = [
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.prod.yml"
        ]

        for compose_file in compose_files:
            file_path = self.project_root / compose_file

            if not file_path.exists():
                results[compose_file] = {
                    "valid": False,
                    "error": f"{compose_file} 不存在"
                }
                continue

            try:
                # 使用 docker-compose config 進行語法檢查
                result = subprocess.run([
                    "docker-compose", "-f", str(file_path), "config"
                ], check=False, capture_output=True, text=True, cwd=self.project_root, timeout=30)

                results[compose_file] = {
                    "valid": result.returncode == 0,
                    "stdout": result.stdout[:500] if result.stdout else "",
                    "stderr": result.stderr[:500] if result.stderr else "",
                    "return_code": result.returncode
                }

            except subprocess.TimeoutExpired:
                results[compose_file] = {
                    "valid": False,
                    "error": f"{compose_file} 語法檢查超時"
                }
            except FileNotFoundError:
                results[compose_file] = {
                    "valid": False,
                    "error": "docker-compose 未安裝或不在 PATH 中"
                }
            except Exception as e:
                results[compose_file] = {
                    "valid": False,
                    "error": f"{compose_file} 語法檢查失敗: {e!s}"
                }

        return results

    def test_yaml_configuration_files(self) -> dict[str, Any]:
        """測試 YAML 配置文件語法"""
        results = {}

        # 查找所有 YAML 配置文件
        yaml_files = []
        for pattern in ["*.yml", "*.yaml"]:
            yaml_files.extend(self.project_root.glob(pattern))
            yaml_files.extend(self.project_root.glob(f"configs/{pattern}"))
            yaml_files.extend(self.project_root.glob(f".github/workflows/{pattern}"))

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, encoding='utf-8') as f:
                    yaml.safe_load(f)

                results[str(yaml_file.relative_to(self.project_root))] = {
                    "valid": True
                }

            except yaml.YAMLError as e:
                results[str(yaml_file.relative_to(self.project_root))] = {
                    "valid": False,
                    "error": f"YAML 語法錯誤: {e!s}"
                }
            except Exception as e:
                results[str(yaml_file.relative_to(self.project_root))] = {
                    "valid": False,
                    "error": f"文件讀取失敗: {e!s}"
                }

        return results

    def test_deployment_scripts(self) -> dict[str, Any]:
        """測試部署腳本語法"""
        results = {}

        if not self.scripts_path.exists():
            return {"error": "scripts 目錄不存在"}

        # 查找所有腳本文件
        script_files = []
        for pattern in ["*.sh", "*.py"]:
            script_files.extend(self.scripts_path.glob(pattern))

        for script_file in script_files:
            if script_file.suffix == '.sh':
                result = self._test_shell_script(script_file)
            elif script_file.suffix == '.py':
                result = self._test_python_script(script_file)
            else:
                result = {"valid": True, "skipped": "未知腳本類型"}

            results[str(script_file.relative_to(self.project_root))] = result

        return results

    def _test_shell_script(self, script_path: Path) -> dict[str, Any]:
        """測試 Shell 腳本語法"""
        try:
            # 使用 bash -n 進行語法檢查
            result = subprocess.run([
                "bash", "-n", str(script_path)
            ], check=False, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # 檢查腳本權限
                is_executable = os.access(script_path, os.X_OK)
                return {
                    "valid": True,
                    "executable": is_executable,
                    "warning": "腳本不可執行" if not is_executable else None
                }
            else:
                return {
                    "valid": False,
                    "error": result.stderr or "Shell 腳本語法錯誤"
                }

        except FileNotFoundError:
            return {"valid": False, "error": "Bash 未安裝或不在 PATH 中"}
        except Exception as e:
            return {"valid": False, "error": f"Shell 腳本檢查失敗: {e!s}"}

    def _test_python_script(self, script_path: Path) -> dict[str, Any]:
        """測試 Python 腳本語法"""
        try:
            with open(script_path, encoding='utf-8') as f:
                content = f.read()

            # 編譯檢查語法
            compile(content, str(script_path), 'exec')

            return {"valid": True}

        except SyntaxError as e:
            return {
                "valid": False,
                "error": f"Python 語法錯誤: {e.msg} (行 {e.lineno})"
            }
        except Exception as e:
            return {"valid": False, "error": f"Python 腳本檢查失敗: {e!s}"}

    def test_environment_file_templates(self) -> dict[str, Any]:
        """測試環境文件範本"""
        results = {}

        env_templates = [
            ".env.example",
            ".env.development.template",
            ".env.production.template"
        ]

        for env_file in env_templates:
            file_path = self.project_root / env_file

            if not file_path.exists():
                results[env_file] = {
                    "exists": False,
                    "recommended": True
                }
                continue

            try:
                with open(file_path, encoding='utf-8') as f:
                    content = f.read()

                # 檢查是否包含敏感資料
                sensitive_patterns = [
                    r'TOKEN=\w+',  # 實際 token
                    r'PASSWORD=\w+',  # 實際密碼
                    r'SECRET=\w+',  # 實際密鑰
                ]

                issues = []
                for pattern in sensitive_patterns:
                    import re
                    if re.search(pattern, content):
                        issues.append(f"包含敏感資料模式: {pattern}")

                results[env_file] = {
                    "exists": True,
                    "valid": len(issues) == 0,
                    "issues": issues
                }

            except Exception as e:
                results[env_file] = {
                    "exists": True,
                    "valid": False,
                    "error": f"文件檢查失敗: {e!s}"
                }

        return results

    def test_github_workflows(self) -> dict[str, Any]:
        """測試 GitHub Actions 工作流程"""
        workflows_path = self.project_root / ".github" / "workflows"

        if not workflows_path.exists():
            return {"error": "GitHub workflows 目錄不存在"}

        results = {}
        workflow_files = list(workflows_path.glob("*.yml")) + list(workflows_path.glob("*.yaml"))

        for workflow_file in workflow_files:
            try:
                with open(workflow_file, encoding='utf-8') as f:
                    workflow_data = yaml.safe_load(f)

                # 基本結構檢查
                required_fields = ['name', 'on', 'jobs']
                missing_fields = [field for field in required_fields if field not in workflow_data]

                issues = []
                if missing_fields:
                    issues.append(f"缺少必要欄位: {missing_fields}")

                # 檢查 jobs 結構
                jobs = workflow_data.get('jobs', {})
                if not jobs:
                    issues.append("沒有定義任何 job")

                for job_name, job_data in jobs.items():
                    if 'runs-on' not in job_data:
                        issues.append(f"Job '{job_name}' 缺少 runs-on")
                    if 'steps' not in job_data:
                        issues.append(f"Job '{job_name}' 缺少 steps")

                results[str(workflow_file.relative_to(self.project_root))] = {
                    "valid": len(issues) == 0,
                    "issues": issues,
                    "jobs_count": len(jobs)
                }

            except yaml.YAMLError as e:
                results[str(workflow_file.relative_to(self.project_root))] = {
                    "valid": False,
                    "error": f"YAML 格式錯誤: {e!s}"
                }
            except Exception as e:
                results[str(workflow_file.relative_to(self.project_root))] = {
                    "valid": False,
                    "error": f"工作流程檢查失敗: {e!s}"
                }

        return results

    def test_docker_build(self) -> dict[str, Any]:
        """測試 Docker 映像建置（僅語法檢查，不實際建置）"""
        try:
            client = docker.from_env()

            # 檢查 Docker 是否可用
            client.ping()

            dockerfile_path = self.project_root / "Dockerfile"
            if not dockerfile_path.exists():
                return {"buildable": False, "error": "Dockerfile 不存在"}

            # 使用 Docker API 進行建置語法檢查
            try:
                # 僅檢查建置上下文和 Dockerfile 語法
                build_logs = client.api.build(
                    path=str(self.project_root),
                    dockerfile="Dockerfile",
                    pull=False,
                    nocache=False,
                    rm=True,
                    forcerm=True,
                    decode=True,
                    tag="discord-bot-test:syntax-check"
                )

                # 檢查建置日誌中的錯誤
                errors = []
                for log in build_logs:
                    if 'error' in log:
                        errors.append(log['error'])
                    elif 'stream' in log and 'error' in log['stream'].lower():
                        errors.append(log['stream'])

                return {
                    "buildable": len(errors) == 0,
                    "errors": errors[:5],  # 只保留前 5 個錯誤
                    "note": "這是語法檢查，未完成完整建置"
                }

            except DockerException as e:
                return {
                    "buildable": False,
                    "error": f"Docker 建置檢查失敗: {e!s}"
                }

        except DockerException:
            return {
                "buildable": False,
                "error": "無法連接到 Docker，請確認 Docker 服務正在運行"
            }
        except Exception as e:
            return {
                "buildable": False,
                "error": f"Docker 建置測試失敗: {e!s}"
            }


# Pytest 測試函數
@pytest.fixture
def deployment_tester():
    """部署測試器 fixture"""
    return DeploymentTester()


def test_docker_files_exist(deployment_tester):
    """測試 Docker 文件存在"""
    results = deployment_tester.test_docker_files_exist()

    missing_files = [
        file_name for file_name, result in results.items()
        if not result["exists"]
    ]

    # Dockerfile 和 docker-compose.yml 是必須的
    critical_files = ["Dockerfile", "docker-compose.yml"]
    missing_critical = [f for f in missing_files if f in critical_files]

    assert len(missing_critical) == 0, f"缺少關鍵 Docker 文件: {missing_critical}"


def test_dockerfile_syntax_valid(deployment_tester):
    """測試 Dockerfile 語法正確"""
    result = deployment_tester.test_dockerfile_syntax()

    if "error" in result and "Docker 未安裝" in result["error"]:
        pytest.skip("Docker 未安裝，跳過 Dockerfile 語法檢查")

    assert result["valid"], f"Dockerfile 語法錯誤: {result.get('stderr', result.get('error', ''))}"


def test_docker_compose_syntax_valid(deployment_tester):
    """測試 Docker Compose 文件語法正確"""
    results = deployment_tester.test_docker_compose_syntax()

    # 檢查是否有 docker-compose 可用
    if any("docker-compose 未安裝" in r.get("error", "") for r in results.values()):
        pytest.skip("docker-compose 未安裝，跳過語法檢查")

    invalid_files = [
        file_name for file_name, result in results.items()
        if not result.get("valid", False) and "不存在" not in result.get("error", "")
    ]

    assert len(invalid_files) == 0, f"以下 Docker Compose 文件語法錯誤: {invalid_files}"


def test_yaml_files_valid(deployment_tester):
    """測試 YAML 配置文件語法正確"""
    results = deployment_tester.test_yaml_configuration_files()

    invalid_files = [
        file_name for file_name, result in results.items()
        if not result.get("valid", False)
    ]

    assert len(invalid_files) == 0, f"以下 YAML 文件語法錯誤: {invalid_files}"


def test_deployment_scripts_valid(deployment_tester):
    """測試部署腳本語法正確"""
    results = deployment_tester.test_deployment_scripts()

    if "error" in results:
        pytest.skip(f"腳本測試跳過: {results['error']}")

    invalid_scripts = [
        script_name for script_name, result in results.items()
        if not result.get("valid", False)
    ]

    assert len(invalid_scripts) == 0, f"以下腳本語法錯誤: {invalid_scripts}"


def test_environment_templates_safe(deployment_tester):
    """測試環境文件範本安全"""
    results = deployment_tester.test_environment_file_templates()

    unsafe_files = [
        file_name for file_name, result in results.items()
        if result.get("exists", False) and not result.get("valid", True)
    ]

    assert len(unsafe_files) == 0, f"以下環境文件範本包含敏感資料: {unsafe_files}"


def test_github_workflows_valid(deployment_tester):
    """測試 GitHub Actions 工作流程有效"""
    results = deployment_tester.test_github_workflows()

    if "error" in results:
        pytest.skip(f"GitHub workflows 測試跳過: {results['error']}")

    invalid_workflows = [
        workflow_name for workflow_name, result in results.items()
        if not result.get("valid", False)
    ]

    assert len(invalid_workflows) == 0, f"以下 GitHub workflow 無效: {invalid_workflows}"


if __name__ == "__main__":
    # 獨立運行時進行完整測試
    tester = DeploymentTester()

    print("=== Docker 文件檢查 ===")
    docker_files = tester.test_docker_files_exist()
    print(json.dumps(docker_files, indent=2, ensure_ascii=False))

    print("\n=== Docker Compose 語法檢查 ===")
    compose_results = tester.test_docker_compose_syntax()
    print(json.dumps(compose_results, indent=2, ensure_ascii=False))

    print("\n=== 部署腳本檢查 ===")
    scripts_results = tester.test_deployment_scripts()
    print(json.dumps(scripts_results, indent=2, ensure_ascii=False))
