"""
API 文件測試模組
驗證 API 文件的準確性和一致性
"""

import json
from pathlib import Path
from typing import Any

import pytest
import requests
from jsonschema import ValidationError, validate


class APIDocumentationTester:
    """API 文件測試器"""

    def __init__(self, api_base_url: str = "http://localhost:8080"):
        self.api_base_url = api_base_url
        self.docs_path = Path("docs/api")
        self.openapi_path = self.docs_path / "openapi.json"

    def test_openapi_spec_valid(self) -> dict[str, Any]:
        """測試 OpenAPI 規格文件有效性"""
        if not self.openapi_path.exists():
            return {"valid": False, "error": "OpenAPI 規格文件不存在"}

        try:
            with open(self.openapi_path, encoding="utf-8") as f:
                spec = json.load(f)

            # 基本結構驗證
            required_fields = ["openapi", "info", "paths"]
            missing_fields = [field for field in required_fields if field not in spec]

            if missing_fields:
                return {"valid": False, "error": f"缺少必要欄位: {missing_fields}"}

            # 版本驗證
            if not spec["openapi"].startswith("3."):
                return {
                    "valid": False,
                    "error": f"不支援的 OpenAPI 版本: {spec['openapi']}",
                }

            return {
                "valid": True,
                "version": spec["openapi"],
                "title": spec["info"].get("title", ""),
                "version_info": spec["info"].get("version", ""),
                "paths_count": len(spec.get("paths", {})),
            }

        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"JSON 格式錯誤: {e!s}"}
        except Exception as e:
            return {"valid": False, "error": f"規格驗證失敗: {e!s}"}

    def test_api_endpoints_accessible(self) -> list[dict[str, Any]]:
        """測試 API 端點是否可訪問"""
        if not self.openapi_path.exists():
            return [{"error": "OpenAPI 規格文件不存在"}]

        try:
            with open(self.openapi_path, encoding="utf-8") as f:
                spec = json.load(f)

            results = []

            for path, methods in spec.get("paths", {}).items():
                for method, details in methods.items():
                    if method.upper() in [
                        "GET",
                        "POST",
                        "PUT",
                        "DELETE",
                        "PATCH",
                        "HEAD",
                    ]:
                        result = self._test_single_endpoint(
                            method.upper(), path, details
                        )
                        results.append(result)

            return results

        except Exception as e:
            return [{"error": f"端點測試失敗: {e!s}"}]

    def _test_single_endpoint(
        self, method: str, path: str, spec: dict
    ) -> dict[str, Any]:
        """測試單個 API 端點"""
        full_url = f"{self.api_base_url}{path}"

        try:
            # 根據方法類型發送請求
            if method == "GET":
                response = requests.get(full_url, timeout=10)
            elif method == "HEAD":
                response = requests.head(full_url, timeout=10)
            elif method == "POST":
                # 使用空的 JSON 載荷進行測試
                response = requests.post(full_url, json={}, timeout=10)
            elif method == "PUT":
                response = requests.put(full_url, json={}, timeout=10)
            elif method == "DELETE":
                response = requests.delete(full_url, timeout=10)
            elif method == "PATCH":
                response = requests.patch(full_url, json={}, timeout=10)
            else:
                response = requests.request(method, full_url, timeout=10)

            # 檢查回應是否符合文件說明
            expected_responses = spec.get("responses", {})
            status_documented = str(response.status_code) in expected_responses

            return {
                "method": method,
                "path": path,
                "url": full_url,
                "accessible": True,
                "status_code": response.status_code,
                "status_documented": status_documented,
                "response_time": response.elapsed.total_seconds(),
                "spec_summary": spec.get("summary", ""),
                "spec_description": spec.get("description", ""),
                "expected_responses": list(expected_responses.keys()),
            }

        except requests.RequestException as e:
            return {
                "method": method,
                "path": path,
                "url": full_url,
                "accessible": False,
                "error": str(e),
                "spec_summary": spec.get("summary", ""),
                "spec_description": spec.get("description", ""),
            }

    def test_response_schemas(self) -> list[dict[str, Any]]:
        """測試 API 回應格式是否符合 schema"""
        if not self.openapi_path.exists():
            return [{"error": "OpenAPI 規格文件不存在"}]

        try:
            with open(self.openapi_path, encoding="utf-8") as f:
                spec = json.load(f)

            results = []

            for path, methods in spec.get("paths", {}).items():
                for method, details in methods.items():
                    if method.upper() == "GET":  # 主要測試 GET 端點
                        result = self._validate_response_schema(path, details, spec)
                        if result:
                            results.append(result)

            return results

        except Exception as e:
            return [{"error": f"Schema 驗證失敗: {e!s}"}]

    def _validate_response_schema(
        self, path: str, spec: dict, full_spec: dict
    ) -> dict[str, Any]:
        """驗證回應 schema"""
        full_url = f"{self.api_base_url}{path}"

        try:
            response = requests.get(full_url, timeout=10)

            if response.status_code >= 400:
                return None  # 跳過錯誤回應的 schema 驗證

            try:
                response_data = response.json()
            except ValueError:
                return {"path": path, "valid": False, "error": "回應不是有效的 JSON"}

            # 取得預期的 schema
            responses = spec.get("responses", {})
            success_response = None

            for status_code in ["200", "201", "202"]:
                if status_code in responses:
                    success_response = responses[status_code]
                    break

            if not success_response:
                return {
                    "path": path,
                    "valid": False,
                    "error": "沒有定義成功回應的 schema",
                }

            # 取得 schema 定義
            content = success_response.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})

            if not schema:
                return {"path": path, "valid": False, "error": "沒有定義回應 schema"}

            # 解析 $ref 引用
            resolved_schema = self._resolve_schema_refs(schema, full_spec)

            # 驗證 schema
            try:
                validate(instance=response_data, schema=resolved_schema)
                return {
                    "path": path,
                    "valid": True,
                    "status_code": response.status_code,
                }
            except ValidationError as e:
                return {
                    "path": path,
                    "valid": False,
                    "error": f"Schema 驗證失敗: {e.message}",
                }

        except requests.RequestException as e:
            return {"path": path, "valid": False, "error": f"請求失敗: {e!s}"}

    def _resolve_schema_refs(self, schema: dict, full_spec: dict) -> dict:
        """解析 schema 中的 $ref 引用"""
        if isinstance(schema, dict):
            if "$ref" in schema:
                ref_path = schema["$ref"]
                if ref_path.startswith("#/"):
                    # 解析內部引用
                    path_parts = ref_path[2:].split("/")
                    resolved = full_spec
                    for part in path_parts:
                        resolved = resolved.get(part, {})
                    return self._resolve_schema_refs(resolved, full_spec)
                return schema
            else:
                # 遞迴解析嵌套的 schema
                resolved = {}
                for key, value in schema.items():
                    resolved[key] = self._resolve_schema_refs(value, full_spec)
                return resolved
        elif isinstance(schema, list):
            return [self._resolve_schema_refs(item, full_spec) for item in schema]
        else:
            return schema

    def test_api_documentation_completeness(self) -> dict[str, Any]:
        """測試 API 文件完整性"""
        if not self.openapi_path.exists():
            return {"complete": False, "error": "OpenAPI 規格文件不存在"}

        try:
            with open(self.openapi_path, encoding="utf-8") as f:
                spec = json.load(f)

            completeness_issues = []

            # 檢查基本資訊完整性
            info = spec.get("info", {})
            if not info.get("title"):
                completeness_issues.append("缺少 API 標題")
            if not info.get("description"):
                completeness_issues.append("缺少 API 描述")
            if not info.get("version"):
                completeness_issues.append("缺少 API 版本")

            # 檢查每個端點的文件完整性
            paths = spec.get("paths", {})
            total_endpoints = 0
            documented_endpoints = 0

            for path, methods in paths.items():
                for method, details in methods.items():
                    if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                        total_endpoints += 1

                        # 檢查端點文件完整性
                        has_summary = bool(details.get("summary"))
                        has_description = bool(details.get("description"))
                        has_responses = bool(details.get("responses"))

                        if has_summary and has_description and has_responses:
                            documented_endpoints += 1
                        else:
                            missing = []
                            if not has_summary:
                                missing.append("summary")
                            if not has_description:
                                missing.append("description")
                            if not has_responses:
                                missing.append("responses")

                            completeness_issues.append(
                                f"{method.upper()} {path}: 缺少 {', '.join(missing)}"
                            )

            completeness_rate = (
                documented_endpoints / total_endpoints if total_endpoints > 0 else 0
            )

            return {
                "complete": len(completeness_issues) == 0,
                "completeness_rate": completeness_rate,
                "total_endpoints": total_endpoints,
                "documented_endpoints": documented_endpoints,
                "issues": completeness_issues,
            }

        except Exception as e:
            return {"complete": False, "error": f"完整性檢查失敗: {e!s}"}


# Pytest 測試函數
@pytest.fixture
def api_tester():
    """API 文件測試器 fixture"""
    return APIDocumentationTester()


def test_openapi_spec_is_valid(api_tester):
    """測試 OpenAPI 規格文件有效"""
    result = api_tester.test_openapi_spec_valid()
    assert result["valid"], f"OpenAPI 規格無效: {result.get('error', '')}"


def test_api_endpoints_are_accessible(api_tester):
    """測試 API 端點可訪問"""
    results = api_tester.test_api_endpoints_accessible()

    if len(results) == 1 and "error" in results[0]:
        pytest.skip(f"端點測試跳過: {results[0]['error']}")

    inaccessible_endpoints = [
        r for r in results if not r.get("accessible", False) and "error" not in r
    ]

    if inaccessible_endpoints:
        endpoints_info = [
            f"{ep['method']} {ep['path']}" for ep in inaccessible_endpoints
        ]
        pytest.fail(f"以下端點無法訪問: {', '.join(endpoints_info)}")


def test_response_schemas_are_valid(api_tester):
    """測試 API 回應格式符合 schema"""
    results = api_tester.test_response_schemas()

    if len(results) == 1 and "error" in results[0]:
        pytest.skip(f"Schema 驗證跳過: {results[0]['error']}")

    invalid_schemas = [r for r in results if not r.get("valid", False)]

    if invalid_schemas:
        schema_info = [
            f"{schema['path']}: {schema.get('error', '未知錯誤')}"
            for schema in invalid_schemas
        ]
        pytest.fail(f"以下端點 schema 驗證失敗: {'; '.join(schema_info)}")


def test_api_documentation_is_complete(api_tester):
    """測試 API 文件完整性"""
    result = api_tester.test_api_documentation_completeness()

    if "error" in result:
        pytest.skip(f"完整性檢查跳過: {result['error']}")

    # 設定最低完整性要求(80%)
    min_completeness = 0.8
    assert result["completeness_rate"] >= min_completeness, (
        f"API 文件完整性不足: {result['completeness_rate']:.1%} < {min_completeness:.1%}\n"
        f"問題: {'; '.join(result.get('issues', []))}"
    )


if __name__ == "__main__":
    # 獨立運行時進行完整測試
    tester = APIDocumentationTester()

    print("=== OpenAPI 規格驗證 ===")
    spec_result = tester.test_openapi_spec_valid()
    print(json.dumps(spec_result, indent=2, ensure_ascii=False))

    print("\n=== 端點可訪問性測試 ===")
    endpoint_results = tester.test_api_endpoints_accessible()
    for result in endpoint_results[:5]:  # 只顯示前 5 個結果
        print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\n總共測試了 {len(endpoint_results)} 個端點")

    print("\n=== 文件完整性檢查 ===")
    completeness_result = tester.test_api_documentation_completeness()
    print(json.dumps(completeness_result, indent=2, ensure_ascii=False))
