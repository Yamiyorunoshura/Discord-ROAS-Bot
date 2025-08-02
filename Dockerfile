# Discord ROAS Bot - Production Dockerfile
# 多階段構建：依賴安裝 → 最終運行環境
# 優化：最小化映像大小、提升安全性、加快構建速度

# ============================================================================
# 階段 1: 依賴基礎映像
# ============================================================================
FROM python:3.12-slim as dependencies

# 設定標籤和維護資訊
LABEL maintainer="ADR Bot Team <admin@adrbot.dev>"
LABEL version="2.0.0"
LABEL description="Discord ROAS Bot - Advanced Discord server management bot"

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_CACHE_DIR=/tmp/uv-cache

# 建立非 root 用戶
RUN groupadd --gid 1000 botuser && \
    useradd --uid 1000 --gid botuser --shell /bin/bash --create-home botuser

# 安裝系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基本工具
    curl \
    ca-certificates \
    # 編譯工具 (用於一些 Python 套件)
    gcc \
    g++ \
    make \
    # 圖像處理依賴
    libjpeg62-turbo-dev \
    libpng-dev \
    libfreetype6-dev \
    zlib1g-dev \
    # 清理
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# 安裝 UV 包管理器
RUN pip install uv==0.4.15

# 設定工作目錄
WORKDIR /app

# 切換到非 root 用戶
USER botuser

# 複製依賴文件
COPY --chown=botuser:botuser pyproject.toml uv.lock ./

# 使用 UV 安裝依賴到 /app/.venv
RUN uv sync --frozen --no-dev

# ============================================================================
# 階段 2: 生產運行環境
# ============================================================================
FROM python:3.12-slim as production

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PATH="/app/.venv/bin:$PATH" \
    # Discord.py 優化
    DISCORD_ENABLE_DEBUG_EVENTS=0 \
    # 效能優化
    MALLOC_TRIM_THRESHOLD_=65536 \
    MALLOC_MMAP_THRESHOLD_=65536

# 複製非 root 用戶配置
RUN groupadd --gid 1000 botuser && \
    useradd --uid 1000 --gid botuser --shell /bin/bash --create-home botuser

# 安裝運行時系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基本運行時
    ca-certificates \
    # 圖像處理運行時庫
    libjpeg62-turbo \
    libpng16-16 \
    libfreetype6 \
    zlib1g \
    # 字體支援 (用於圖像生成)
    fonts-noto-cjk \
    # 健康檢查工具
    curl \
    # 清理
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# 設定工作目錄
WORKDIR /app

# 從依賴階段複製虛擬環境
COPY --from=dependencies --chown=botuser:botuser /app/.venv /app/.venv

# 複製應用程式碼
COPY --chown=botuser:botuser src/ ./src/
COPY --chown=botuser:botuser scripts/ ./scripts/
COPY --chown=botuser:botuser docs/ ./docs/
COPY --chown=botuser:botuser *.py ./
COPY --chown=botuser:botuser *.md ./
COPY --chown=botuser:botuser *.toml ./

# 建立必要目錄
RUN mkdir -p logs dbs cache assets && \
    chown -R botuser:botuser logs dbs cache assets

# 切換到非 root 用戶
USER botuser

# 設定資料卷
VOLUME ["/app/dbs", "/app/logs", "/app/cache", "/app/assets"]

# 暴露端口 (如果需要 API 服務)
EXPOSE 8080

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || python -c "import sys; sys.exit(0)"

# 設定入口點和預設命令
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--production"]

# ============================================================================
# 開發環境映像
# ============================================================================
FROM dependencies as development

# 安裝開發依賴
RUN uv sync --frozen

# 安裝額外開發工具
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    htop \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER botuser

# 複製完整專案 (包含測試和開發工具)
COPY --chown=botuser:botuser . .

# 開發環境入口點
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--development"]

# ============================================================================
# 測試環境映像  
# ============================================================================
FROM development as testing

# 運行測試
RUN uv run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# 運行代碼品質檢查
RUN uv run ruff check src/ && \
    uv run mypy src/ && \
    uv run black --check src/

# 測試入口點
ENTRYPOINT ["uv", "run", "pytest"]
CMD ["tests/", "-v"]