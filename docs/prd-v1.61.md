# Discord ADR Bot v1.61 核心需求文件

## 📋 需求概述

本文件定義了 Discord ADR Bot v1.61 的核心功能完善需求，旨在提升用戶體驗和系統完整性。

### 🎯 總體目標
- 完善所有模塊的用戶界面面板
- 提升訊息監聽模塊的視覺效果和智能化
- 修復歡迎模塊的圖片生成問題
- 設計更具吸引力的活躍度進度條
- 確保所有功能模塊的一致性和穩定性

---

## 📊 需求分析

### 1. 完成各個模塊的面板 (Priority: High)

#### 1.1 問題分析
經過代碼審查，發現以下模塊面板狀態：
- ✅ **已完成**: `anti_executable`, `anti_link`, `welcome`, `activity_meter`
- ⚠️ **部分完成**: `message_listener` (基本面板存在，但功能不完整)
- ❌ **缺失**: `anti_spam`, `sync_data` (面板檔案為空或不存在)

#### 1.2 具體需求

**1.2.1 Anti-Spam 模塊面板**
- **檔案位置**: `cogs/protection/anti_spam/panel/main_view.py`
- **當前狀態**: 檔案為空
- **需求功能**:
  - 垃圾訊息檢測開關
  - 檢測靈敏度設定 (低/中/高)
  - 白名單管理 (用戶/角色)
  - 處罰設定 (警告/禁言/踢出)
  - 統計資訊顯示
  - 日誌頻道設定

**1.2.2 Sync Data 模塊面板**
- **檔案位置**: `cogs/sync_data/panel/` (需新建整個目錄結構)
- **當前狀態**: 無面板系統
- **需求功能**:
  - 同步狀態顯示 (上次同步時間、狀態)
  - 手動同步觸發按鈕
  - 自動同步設定 (間隔時間)
  - 同步歷史記錄查看
  - 同步範圍選擇 (角色/頻道/完整)

**1.2.3 Message Listener 模塊面板完善**
- **檔案位置**: `cogs/message_listener/panel/main_view.py`
- **當前狀態**: 基本面板存在，但功能不完整
- **需求功能**:
  - 批量大小動態調整界面
  - 圖片品質設定選項
  - 字體選擇和大小調整
  - 顏色主題自定義
  - 渲染預覽功能

#### 1.3 技術實現方案

**1.3.1 統一面板架構**
```python
# 每個模塊面板應包含以下標準組件:
class ModuleMainView(discord.ui.View):
    def __init__(self, cog, guild_id: int, user_id: int):
        # 標準初始化
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.current_panel = "main"
        
    # 標準方法
    async def switch_panel(self, panel_name: str, interaction: discord.Interaction)
    async def refresh_panel(self, interaction: discord.Interaction)
    async def _handle_error(self, interaction: discord.Interaction, error: str)
```

**1.3.2 組件標準化**
- 統一的按鈕樣式和行為
- 標準化的選擇器組件
- 一致的錯誤處理機制
- 統一的權限檢查邏輯

---

### 2. 訊息監聽渲染的圖片更貼合 Discord 實際聊天框風格 (Priority: High)

#### 2.1 問題分析
當前 `MessageRenderer` 類存在以下問題：
- 色彩搭配與 Discord 官方不完全一致
- 字體渲染效果需要優化
- 頭像圓角處理不夠精細
- 訊息氣泡和間距需要調整

#### 2.2 具體需求

**2.2.1 視覺風格優化**
- **背景色調**: 完全匹配 Discord 深色主題
  - 主背景: `#36393f` (替代當前的 `(54, 57, 63)`)
  - 訊息區域: `#40444b`
  - 懸停效果: `#32353b`
- **文字顏色**: 
  - 主文字: `#dcddde` (替代當前的 `(220, 221, 222)`)
  - 次要文字: `#72767d`
  - 用戶名: `#ffffff`
- **頭像優化**:
  - 完美圓形裁剪
  - 添加狀態指示器 (在線/離線)
  - 支援動態頭像預覽

**2.2.2 排版和間距**
- 訊息間距: 8px (當前 10px)
- 左側頭像區域: 62px (當前 50px)
- 訊息氣泡圓角: 8px
- 時間戳位置: 更貼近用戶名

#### 2.3 技術實現方案

**2.3.1 色彩常數更新**
```python
# 在 cogs/message_listener/config/config.py 中更新
DISCORD_COLORS = {
    'bg_primary': (54, 57, 63),      # #36393f
    'bg_secondary': (64, 68, 75),    # #40444b
    'bg_tertiary': (50, 53, 59),     # #32353b
    'text_primary': (220, 221, 222), # #dcddde
    'text_secondary': (114, 118, 125), # #72767d
    'text_username': (255, 255, 255), # #ffffff
    'accent_blurple': (88, 101, 242), # #5865f2
}
```

**2.3.2 渲染引擎優化**
- 實現訊息氣泡效果
- 添加懸停視覺效果
- 優化字體渲染質量
- 實現更精確的時間戳格式

---

### 3. 訊息監聽模塊智能批量調整 (Priority: Medium)

#### 3.1 問題分析
當前批量處理機制固定，無法根據實際情況動態調整：
- 固定的 `MAX_CACHED_MESSAGES = 10`
- 固定的 `MAX_CACHE_TIME = 600`
- 無法根據圖片大小和訊息內容自動調整

#### 3.2 具體需求

**3.2.1 智能批量算法**
- **基於內容長度**: 長訊息減少批量大小
- **基於圖片數量**: 多圖片訊息減少批量大小
- **基於頻道活躍度**: 活躍頻道增加批量大小
- **基於渲染時間**: 根據歷史渲染時間動態調整

**3.2.2 配置參數**
```python
# 智能批量配置
SMART_BATCH_CONFIG = {
    'min_batch_size': 3,
    'max_batch_size': 15,
    'base_batch_size': 8,
    'content_length_threshold': 200,  # 字符數
    'image_count_threshold': 2,       # 圖片數
    'render_time_threshold': 5.0,     # 秒
    'activity_threshold': 10,         # 訊息/分鐘
}
```

#### 3.3 技術實現方案

**3.3.1 智能批量計算器**
```python
class SmartBatchCalculator:
    def calculate_optimal_batch_size(self, 
                                   messages: List[discord.Message],
                                   channel_activity: float,
                                   last_render_time: float) -> int:
        # 實現智能批量計算邏輯
        pass
```

**3.3.2 性能監控**
- 記錄每次渲染的時間
- 監控圖片大小和質量
- 追蹤用戶體驗指標

---

### 4. 歡迎模塊圖片生成問題修復 (Priority: Critical)

#### 4.1 問題分析
通過代碼審查發現 `WelcomeRenderer` 存在以下問題：
- 頭像下載失敗時缺少錯誤處理
- 圖片比例計算不正確
- 標題和描述位置偏移
- 字體載入失敗的回退機制不完善

#### 4.2 具體需求

**4.2.1 頭像處理優化**
- **下載重試機制**: 3次重試，逐漸增加間隔
- **格式支援**: 支援 PNG, JPG, WebP, GIF
- **大小調整**: 智能裁剪和縮放
- **錯誤回退**: 使用預設頭像圖片

**4.2.2 圖片比例修正**
- **標準比例**: 16:9 (推薦) 或 4:3
- **響應式佈局**: 根據內容長度調整高度
- **最小/最大尺寸**: 600x240 到 1200x480

**4.2.3 文字渲染改進**
- **字體回退鏈**: 多級字體載入
- **文字自動換行**: 超長文字智能換行
- **陰影效果**: 提升文字可讀性

#### 4.3 技術實現方案

**4.3.1 頭像下載器重構**
```python
class AvatarDownloader:
    async def download_with_retry(self, url: str, max_retries: int = 3) -> Optional[bytes]:
        for attempt in range(max_retries):
            try:
                # 下載邏輯
                return await self._download_avatar(url)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"頭像下載失敗: {e}")
                    return None
                await asyncio.sleep(2 ** attempt)  # 指數退避
```

**4.3.2 佈局計算器**
```python
class LayoutCalculator:
    def calculate_positions(self, 
                          canvas_size: Tuple[int, int],
                          avatar_size: int,
                          title_length: int,
                          desc_length: int) -> Dict[str, Tuple[int, int]]:
        # 實現智能佈局計算
        pass
```

---

### 5. 設計更有趣更好看的活躍度進度條 (Priority: Medium)

#### 5.1 問題分析
當前進度條設計過於簡單：
- 單一顏色填充
- 缺少動態效果
- 沒有等級或成就系統
- 視覺效果不夠吸引人

#### 5.2 具體需求

**5.2.1 視覺設計升級**
- **漸層效果**: 根據活躍度使用不同顏色漸層
  - 0-25: 灰色到藍色
  - 26-50: 藍色到綠色
  - 51-75: 綠色到黃色
  - 76-100: 黃色到金色
- **動態效果**: 
  - 脈動效果 (高活躍度時)
  - 粒子效果 (滿級時)
  - 光暈效果 (特殊成就時)

**5.2.2 等級系統**
- **等級劃分**: 
  - 新手 (0-10)
  - 活躍 (11-30)
  - 資深 (31-60)
  - 專家 (61-85)
  - 傳奇 (86-100)
- **成就徽章**: 
  - 連續活躍天數
  - 單日最高活躍度
  - 月度排行榜位置

**5.2.3 個性化選項**
- **主題選擇**: 多種顏色主題
- **樣式選擇**: 圓形、方形、六邊形
- **背景選擇**: 純色、漸層、圖案

#### 5.3 技術實現方案

**5.2.1 進度條渲染器重構**
```python
class AdvancedProgressRenderer:
    def __init__(self):
        self.themes = {
            'default': GradientTheme(...),
            'neon': NeonTheme(...),
            'minimal': MinimalTheme(...),
            'gaming': GamingTheme(...),
        }
    
    def render_progress_bar(self, 
                          score: float, 
                          user_level: str,
                          theme: str = 'default',
                          style: str = 'rounded') -> discord.File:
        # 實現高級進度條渲染
        pass
```

**5.2.2 等級系統**
```python
class LevelSystem:
    def get_user_level(self, score: float) -> Dict[str, Any]:
        return {
            'level': self._calculate_level(score),
            'level_name': self._get_level_name(score),
            'next_level_threshold': self._get_next_threshold(score),
            'progress_to_next': self._calculate_progress(score),
            'achievements': self._get_achievements(score),
        }
```

---

## 🧪 測試和驗收標準

### 1. 面板功能測試
- [ ] 所有模塊都有完整的面板界面
- [ ] 面板響應時間 < 2秒
- [ ] 權限檢查正確執行
- [ ] 錯誤處理機制正常工作

### 2. 視覺效果測試
- [ ] 訊息渲染圖片與 Discord 官方風格一致
- [ ] 歡迎圖片正確生成，包含頭像和文字
- [ ] 活躍度進度條顯示正確且美觀
- [ ] 所有圖片在不同設備上正常顯示

### 3. 性能測試
- [ ] 智能批量調整正確工作
- [ ] 圖片渲染時間 < 5秒
- [ ] 記憶體使用量在合理範圍內
- [ ] 並發處理能力測試通過

### 4. 用戶體驗測試
- [ ] 界面操作直觀易懂
- [ ] 錯誤訊息清晰明確
- [ ] 功能回饋及時準確
- [ ] 多語言支援正常

---

## 📈 實施優先級和時程

### Phase 1: 關鍵問題修復 (1-2 週)
1. 修復歡迎模塊圖片生成問題
2. 完成 Anti-Spam 模塊面板
3. 優化訊息監聽渲染效果

### Phase 2: 功能完善 (2-3 週)
1. 完成 Sync Data 模塊面板
2. 實現智能批量調整
3. 完善 Message Listener 面板

### Phase 3: 體驗優化 (1-2 週)
1. 設計新的活躍度進度條
2. 添加等級系統
3. 優化整體用戶體驗

---

## 🔧 技術債務和風險

### 技術債務
1. **字體管理**: 需要統一字體載入和管理機制
2. **圖片快取**: 需要實現智能圖片快取系統
3. **錯誤處理**: 需要統一錯誤處理和日誌記錄
4. **配置管理**: 需要更靈活的配置系統

### 風險評估
1. **性能風險**: 圖片渲染可能影響 Bot 響應速度
2. **記憶體風險**: 大量圖片處理可能導致記憶體洩漏
3. **相容性風險**: 不同 Discord 客戶端的顯示效果可能不一致
4. **維護風險**: 複雜的 UI 系統增加維護成本

---

## 📚 參考資料

1. Discord UI 設計指南
2. PIL/Pillow 圖片處理文檔
3. Discord.py 官方文檔
4. 用戶體驗設計最佳實踐
5. 性能優化指南

---

*本文件版本: v2.0*  
*最後更新: 2024年*  
*負責人: 開發團隊*