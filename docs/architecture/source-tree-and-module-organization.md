# Source Tree and Module Organization

### Project Structure (Actual)

```text
project-root/
├── src/
│   ├── cogs/                    # Discord cog modules
│   │   ├── achievement/         # Achievement system
│   │   ├── activity_meter/      # ROAS calculation core
│   │   ├── welcome/            # Welcome system
│   │   ├── protection/         # Anti-spam protection
│   │   ├── sync_data/          # Data synchronization
│   │   └── message_listener/   # Message monitoring
│   ├── core/                   # Core infrastructure
│   │   ├── database/           # Database models and connections
│   │   ├── testing/            # Testing utilities
│   │   └── utils/              # Shared utilities
│   └── main.py                 # Bot entry point
├── tests/                      # Comprehensive test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── performance/            # Performance tests
│   ├── regression/             # Regression tests
│   ├── conftest.py             # Test configuration (903 lines)
│   └── helpers/                # Test helpers
├── config/                     # Configuration files
├── scripts/                    # Build and deployment scripts
└── docs/                       # Documentation
```

### Key Modules and Their Purpose

- **Activity Meter**: `src/cogs/activity_meter/` - Core ROAS calculation logic
- **Achievement System**: `src/cogs/achievement/` - User achievement tracking
- **Database Core**: `src/core/database/` - SQLAlchemy models and connections
- **Testing Infrastructure**: `tests/conftest.py` - Comprehensive test setup
- **Panel Systems**: `src/cogs/*/panel/` - Discord interactive panels
