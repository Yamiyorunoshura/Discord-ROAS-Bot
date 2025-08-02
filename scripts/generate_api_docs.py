#!/usr/bin/env python3
"""API 文件生成腳本.

此腳本用於生成 Discord ROAS Bot 的完整 API 文件，包含：
- OpenAPI 3.0 規格生成  
- Swagger UI 互動式文件
- API 文件驗證報告
- 多格式輸出支援

使用方式:
    python scripts/generate_api_docs.py
    python scripts/generate_api_docs.py --output docs/api --validate-only
"""

import argparse
import os
import sys
from pathlib import Path

# 設定控制台編碼
if os.name == 'nt':  # Windows
    os.system('chcp 65001 > nul')  # 設定為 UTF-8

# 確保 stdout 使用 UTF-8 編碼
sys.stdout.reconfigure(encoding='utf-8')

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.api_docs import generate_api_documentation


def main():
    """主要執行函數."""
    parser = argparse.ArgumentParser(
        description="生成 Discord ROAS Bot API 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  %(prog)s                                    # 使用預設設定生成文件
  %(prog)s --output docs/api                  # 指定輸出目錄
  %(prog)s --title "My Bot API" --version 1.0 # 自訂標題和版本
  %(prog)s --validate-only                    # 只進行驗證，不生成檔案
        """
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("docs/api"),
        help="輸出目錄路徑 (預設: docs/api)"
    )

    parser.add_argument(
        "--title",
        default="Discord ROAS Bot API",
        help="API 文件標題 (預設: Discord ROAS Bot API)"
    )

    parser.add_argument(
        "--version", "-v",
        default="2.0.0",
        help="API 版本 (預設: 2.0.0)"
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="只進行驗證，不生成實際檔案"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="顯示詳細輸出"
    )

    args = parser.parse_args()

    # 設定日誌級別
    import logging

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger(__name__)

    try:
        logger.info("開始生成 API 文件...")
        logger.info(f"輸出目錄: {args.output}")
        logger.info(f"API 標題: {args.title}")
        logger.info(f"API 版本: {args.version}")

        if args.validate_only:
            logger.info("驗證模式：只進行驗證，不生成檔案")

            # 只進行驗證
            from src.core.api_docs import APIDocumentationValidator, OpenAPIGenerator

            generator = OpenAPIGenerator(args.title, args.version)
            spec = generator.generate_spec()

            validator = APIDocumentationValidator(spec)
            validation_result = validator.validate_spec()

            print("\\n" + "="*60)
            print("API Documentation Validation Results")
            print("="*60)

            if validation_result["valid"]:
                print("✅ Validation passed! Documentation structure is correct.")
            else:
                print("❌ Validation failed! Found the following issues:")

            if validation_result["errors"]:
                print("\\n🚨 Errors:")
                for error in validation_result["errors"]:
                    print(f"  - {error}")

            if validation_result["warnings"]:
                print("\\n⚠️  Warnings:")
                for warning in validation_result["warnings"]:
                    print(f"  - {warning}")

            print(f"\\n📊 Statistics: {validation_result['error_count']} errors, {validation_result['warning_count']} warnings")

            return 0 if validation_result["valid"] else 1

        else:
            # 生成完整文件
            result = generate_api_documentation(
                output_dir=args.output,
                title=args.title,
                version=args.version
            )

            print("\\n" + "="*60)
            print("API Documentation Generation Results")
            print("="*60)

            if result["success"]:
                print("✅ API documentation generated successfully!")
                print("\\n📁 Generated files:")
                for file_path in result["files_generated"]:
                    print(f"  - {file_path}")

                validation = result["validation"]
                if validation["valid"]:
                    print("\\n✅ Documentation validation passed!")
                else:
                    print("\\n⚠️  Documentation validation found issues:")

                if validation["errors"]:
                    print("\\n🚨 Errors:")
                    for error in validation["errors"]:
                        print(f"  - {error}")

                if validation["warnings"]:
                    print("\\n⚠️  Warnings:")
                    for warning in validation["warnings"]:
                        print(f"  - {warning}")

                print(f"\\n📊 Validation stats: {validation['error_count']} errors, {validation['warning_count']} warnings")

                print("\\n🌐 Access methods:")
                print(f"  - Swagger UI: file://{args.output.absolute()}/index.html")
                print(f"  - OpenAPI JSON: file://{args.output.absolute()}/openapi.json")
                print(f"  - Validation report: file://{args.output.absolute()}/validation_report.json")

                return 0

            else:
                print("❌ API documentation generation failed!")
                print(f"Error: {result['error']}")
                return 1

    except KeyboardInterrupt:
        logger.info("\\nOperation interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Unexpected error occurred during execution: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
