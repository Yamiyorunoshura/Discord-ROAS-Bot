# Source Tree

### Existing Project Structure
```
src/
├── core/                    # 核心基礎設施
│   ├── bot.py              # 主 Bot 類別
│   ├── config.py           # 企業級配置管理系統
│   ├── database.py         # 資料庫連線池
│   ├── logger.py           # 日誌系統
│   └── container.py        # 依賴注入容器
├── cogs/                   # 功能模組
│   ├── achievement/        # 成就系統
│   ├── activity_meter/     # 活躍度追蹤
│   ├── currency/          # 貨幣系統
│   ├── government/        # 政府系統
│   ├── message_listener/  # 訊息監聽
│   ├── protection/        # 伺服器保護
│   ├── welcome/          # 歡迎系統
│   └── sync_data/        # 資料同步
└── main.py               # 主要入口點
```

### New File Organization
```
Discord ROAS Bot/
├── src/                           # Existing source code
│   ├── core/                     # Existing core infrastructure
│   │   ├── testing/              # New testing infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── fixtures.py       # Common test fixtures
│   │   │   ├── factories.py      # Test data factories
│   │   │   └── dpytest_config.py # dpytest configuration
│   │   └── quality/              # New quality assurance
│   │       ├── __init__.py
│   │       ├── metrics.py        # Quality metrics collection
│   │       └── enforcement.py    # Quality gate enforcement
│   ├── cogs/                     # Existing cogs with enhancements
│   │   ├── achievement/          # Existing achievement system
│   │   │   └── tests/            # New comprehensive tests
│   │   │       ├── __init__.py
│   │   │       ├── test_achievement_service.py
│   │   │       ├── test_achievement_panel.py
│   │   │       └── test_achievement_integration.py
│   │   └── [similar test structure for all cogs]
├── tests/                        # New comprehensive test suite
│   ├── __init__.py
│   ├── conftest.py              # pytest configuration
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── performance/             # Performance benchmarks
│   └── fixtures/                # Shared test fixtures
└── quality/                     # New quality assurance
    ├── ruff.toml               # ruff configuration
    ├── mypy.ini                # mypy configuration
    └── coverage.ini            # coverage configuration
```

### Integration Guidelines
- **File Naming:** Follow existing snake_case convention, test files prefixed with `test_`
- **Folder Organization:** Mirror existing cog structure in test directories
- **Import/Export Patterns:** Maintain existing relative import patterns, add test-specific imports

