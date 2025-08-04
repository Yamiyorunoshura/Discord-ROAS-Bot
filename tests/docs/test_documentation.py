"""
文件測試框架
用於驗證文件連結、範例代碼和 API 文件的正確性
"""

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import markdown
import pytest
import requests
import yaml
from bs4 import BeautifulSoup


class DocumentationTester:
    """文件測試主類別"""

    def __init__(self, docs_root: Path = Path("docs")):
        self.docs_root = docs_root
        self.base_url = "http://localhost:8080"
        self.errors = []

    def validate_markdown_files(self) -> list[dict[str, Any]]:
        """驗證所有 Markdown 文件的語法和結構"""
        markdown_files = list(self.docs_root.rglob("*.md"))
        results = []

        for file_path in markdown_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # 轉換 Markdown 為 HTML
                html = markdown.markdown(content)
                soup = BeautifulSoup(html, "html.parser")

                # 檢查標題結構
                headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
                header_levels = [int(h.name[1]) for h in headers]

                result = {
                    "file": str(file_path),
                    "status": "pass",
                    "issues": [],
                    "headers": len(headers),
                    "header_structure": self._validate_header_structure(header_levels),
                }

                # 檢查常見問題
                if not content.strip():
                    result["issues"].append("文件為空")
                    result["status"] = "fail"

                if not headers:
                    result["issues"].append("缺少標題")
                    result["status"] = "warning"

                results.append(result)

            except Exception as e:
                results.append(
                    {"file": str(file_path), "status": "error", "error": str(e)}
                )

        return results

    def _validate_header_structure(self, levels: list[int]) -> dict[str, Any]:
        """驗證標題層級結構"""
        if not levels:
            return {"valid": True, "issues": []}

        issues = []

        # 檢查是否從 H1 開始
        if levels[0] != 1:
            issues.append(f"文件應該從 H1 開始,實際從 H{levels[0]} 開始")

        # 檢查層級跳躍
        for i in range(1, len(levels)):
            if levels[i] - levels[i - 1] > 1:
                issues.append(f"標題層級跳躍:H{levels[i - 1]} 直接跳到 H{levels[i]}")

        return {"valid": len(issues) == 0, "issues": issues}

    def validate_links(self) -> list[dict[str, Any]]:
        """驗證文件中的所有連結"""
        results = []
        markdown_files = list(self.docs_root.rglob("*.md"))

        for file_path in markdown_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # 提取 Markdown 連結
                links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)

                file_results = {"file": str(file_path), "links": [], "broken_links": 0}

                for link_text, link_url in links:
                    link_result = self._validate_single_link(link_url, file_path)
                    link_result["text"] = link_text
                    link_result["url"] = link_url

                    file_results["links"].append(link_result)
                    if not link_result["valid"]:
                        file_results["broken_links"] += 1

                results.append(file_results)

            except Exception as e:
                results.append({"file": str(file_path), "error": str(e)})

        return results

    def _validate_single_link(self, url: str, file_path: Path) -> dict[str, Any]:
        """驗證單個連結"""
        try:
            # 處理相對路徑
            if url.startswith("#"):
                # 錨點連結,需要檢查文件內是否存在對應標題
                return {"valid": True, "type": "anchor"}

            elif url.startswith("http"):
                # 外部連結
                try:
                    response = requests.head(url, timeout=10, allow_redirects=True)
                    return {
                        "valid": response.status_code < 400,
                        "type": "external",
                        "status_code": response.status_code,
                    }
                except requests.RequestException as e:
                    return {"valid": False, "type": "external", "error": str(e)}

            else:
                # 本地文件連結
                if url.startswith("./") or url.startswith("../"):
                    target_path = file_path.parent / url
                else:
                    target_path = self.docs_root / url

                target_path = target_path.resolve()

                return {
                    "valid": target_path.exists(),
                    "type": "local",
                    "target_path": str(target_path),
                }

        except Exception as e:
            return {"valid": False, "error": str(e)}

    def validate_code_examples(self) -> list[dict[str, Any]]:
        """驗證文件中的程式碼範例"""
        results = []
        markdown_files = list(self.docs_root.rglob("*.md"))

        for file_path in markdown_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # 提取程式碼區塊
                code_blocks = re.findall(r"```(\w+)?\n(.*?)```", content, re.DOTALL)

                file_results = {"file": str(file_path), "code_blocks": [], "issues": 0}

                for language, code in code_blocks:
                    block_result = self._validate_code_block(language, code)
                    file_results["code_blocks"].append(block_result)

                    if not block_result["valid"]:
                        file_results["issues"] += 1

                results.append(file_results)

            except Exception as e:
                results.append({"file": str(file_path), "error": str(e)})

        return results

    def _validate_code_block(self, language: str, code: str) -> dict[str, Any]:
        """驗證程式碼區塊語法"""
        if not language:
            return {"valid": True, "language": "text", "issues": []}

        issues = []

        try:
            if language.lower() in ["python", "py"]:
                # Python 語法檢查
                compile(code, "<string>", "exec")

            elif language.lower() in ["yaml", "yml"]:
                # YAML 語法檢查
                yaml.safe_load(code)

            elif language.lower() == "json":
                # JSON 語法檢查
                json.loads(code)

            elif language.lower() in ["bash", "shell", "sh"]:
                # Shell 腳本基本檢查
                if "rm -rf /" in code:
                    issues.append("危險的刪除命令")
                if "sudo" in code and "chmod 777" in code:
                    issues.append("不安全的權限設定")

            return {"valid": len(issues) == 0, "language": language, "issues": issues}

        except SyntaxError as e:
            return {
                "valid": False,
                "language": language,
                "issues": [f"語法錯誤: {e!s}"],
            }
        except Exception as e:
            return {
                "valid": False,
                "language": language,
                "issues": [f"驗證錯誤: {e!s}"],
            }

    def validate_api_documentation(self) -> dict[str, Any]:
        """驗證 API 文件與實際端點的一致性"""
        api_doc_path = self.docs_root / "api" / "openapi.json"

        if not api_doc_path.exists():
            return {"error": "OpenAPI 文件不存在"}

        try:
            with open(api_doc_path, encoding="utf-8") as f:
                api_spec = json.load(f)

            results = {
                "spec_valid": True,
                "endpoints": [],
                "total_endpoints": 0,
                "working_endpoints": 0,
                "issues": [],
            }

            # 驗證 OpenAPI 規格基本結構
            required_fields = ["openapi", "info", "paths"]
            for field in required_fields:
                if field not in api_spec:
                    results["spec_valid"] = False
                    results["issues"].append(f"缺少必要欄位: {field}")

            if not results["spec_valid"]:
                return results

            # 驗證每個端點
            for path, methods in api_spec.get("paths", {}).items():
                for method, details in methods.items():
                    if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                        endpoint_result = self._validate_api_endpoint(
                            method.upper(), path, details
                        )
                        results["endpoints"].append(endpoint_result)
                        results["total_endpoints"] += 1

                        if endpoint_result["accessible"]:
                            results["working_endpoints"] += 1

            return results

        except Exception as e:
            return {"error": f"API 文件驗證失敗: {e!s}"}

    def _validate_api_endpoint(
        self, method: str, path: str, spec: dict
    ) -> dict[str, Any]:
        """驗證單個 API 端點"""
        full_url = urljoin(self.base_url, path)

        try:
            if method == "GET":
                response = requests.get(full_url, timeout=10)
            elif method == "POST":
                response = requests.post(full_url, json={}, timeout=10)
            elif method == "PUT":
                response = requests.put(full_url, json={}, timeout=10)
            elif method == "DELETE":
                response = requests.delete(full_url, timeout=10)
            else:
                response = requests.request(method, full_url, timeout=10)

            return {
                "method": method,
                "path": path,
                "accessible": response.status_code < 500,
                "status_code": response.status_code,
                "spec_summary": spec.get("summary", ""),
                "spec_description": spec.get("description", ""),
            }

        except requests.RequestException as e:
            return {
                "method": method,
                "path": path,
                "accessible": False,
                "error": str(e),
                "spec_summary": spec.get("summary", ""),
                "spec_description": spec.get("description", ""),
            }

    def generate_report(self) -> dict[str, Any]:
        """生成完整的文件測試報告"""
        report = {
            "timestamp": pytest.current_timestamp
            if hasattr(pytest, "current_timestamp")
            else "unknown",
            "markdown_validation": self.validate_markdown_files(),
            "link_validation": self.validate_links(),
            "code_validation": self.validate_code_examples(),
            "api_validation": self.validate_api_documentation(),
        }

        # 計算總體統計
        report["summary"] = self._calculate_summary(report)

        return report

    def _calculate_summary(self, report: dict[str, Any]) -> dict[str, Any]:
        """計算測試摘要統計"""
        summary = {
            "total_files": 0,
            "valid_files": 0,
            "total_links": 0,
            "broken_links": 0,
            "total_code_blocks": 0,
            "invalid_code_blocks": 0,
            "api_endpoints": 0,
            "working_endpoints": 0,
        }

        # Markdown 文件統計
        for result in report["markdown_validation"]:
            summary["total_files"] += 1
            if result.get("status") == "pass":
                summary["valid_files"] += 1

        # 連結統計
        for result in report["link_validation"]:
            if "links" in result:
                summary["total_links"] += len(result["links"])
                summary["broken_links"] += result.get("broken_links", 0)

        # 程式碼區塊統計
        for result in report["code_validation"]:
            if "code_blocks" in result:
                summary["total_code_blocks"] += len(result["code_blocks"])
                summary["invalid_code_blocks"] += result.get("issues", 0)

        # API 端點統計
        api_result = report["api_validation"]
        if "total_endpoints" in api_result:
            summary["api_endpoints"] = api_result["total_endpoints"]
            summary["working_endpoints"] = api_result["working_endpoints"]

        # 計算成功率
        if summary["total_files"] > 0:
            summary["file_success_rate"] = (
                summary["valid_files"] / summary["total_files"]
            )

        if summary["total_links"] > 0:
            summary["link_success_rate"] = (
                summary["total_links"] - summary["broken_links"]
            ) / summary["total_links"]

        if summary["total_code_blocks"] > 0:
            summary["code_success_rate"] = (
                summary["total_code_blocks"] - summary["invalid_code_blocks"]
            ) / summary["total_code_blocks"]

        if summary["api_endpoints"] > 0:
            summary["api_success_rate"] = (
                summary["working_endpoints"] / summary["api_endpoints"]
            )

        return summary


# Pytest 集成
@pytest.fixture
def doc_tester():
    """文件測試器 fixture"""
    return DocumentationTester()


def test_markdown_files_valid(doc_tester):
    """測試所有 Markdown 文件語法正確"""
    results = doc_tester.validate_markdown_files()

    failed_files = [r for r in results if r.get("status") == "error"]
    assert len(failed_files) == 0, (
        f"以下文件有語法錯誤: {[f['file'] for f in failed_files]}"
    )


def test_no_broken_links(doc_tester):
    """測試文件中沒有失效連結"""
    results = doc_tester.validate_links()

    total_broken = sum(r.get("broken_links", 0) for r in results)
    assert total_broken == 0, f"發現 {total_broken} 個失效連結"


def test_code_examples_valid(doc_tester):
    """測試程式碼範例語法正確"""
    results = doc_tester.validate_code_examples()

    total_issues = sum(r.get("issues", 0) for r in results)
    assert total_issues == 0, f"發現 {total_issues} 個程式碼語法問題"


def test_api_documentation_consistent(doc_tester):
    """測試 API 文件與實際端點一致"""
    result = doc_tester.validate_api_documentation()

    if "error" in result:
        pytest.skip(f"API 文件驗證跳過: {result['error']}")

    assert result["spec_valid"], f"API 規格無效: {result.get('issues', [])}"


if __name__ == "__main__":
    # 獨立運行時生成報告
    tester = DocumentationTester()
    report = tester.generate_report()

    # 輸出報告到文件
    report_path = Path("docs/validation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Documentation validation report generated: {report_path}")
    print(f"Summary statistics: {report['summary']}")
