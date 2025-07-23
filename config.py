# =============================================================================
# Discord ADR Bot v1.5 - 配置檔案
# =============================================================================
# 功能說明：
# - 集中管理所有 Bot 的配置設定
# - 定義資料庫路徑、日誌路徑、資源路徑
# - 設定活躍度系統參數
# - 提供權限檢查工具函數
# - 時區和時間相關常數
# =============================================================================

import os
import discord
from datetime import timedelta, timezone 
from datetime import timezone as _timezone, timedelta as _timedelta

# =============================================================================
# 1️⃣ 時區與時間常數
# =============================================================================
# 為了向後相容性，保留舊的導入方式
# 同時提供新的時區常數供其他模組使用
timezone = _timezone      # 向後相容：提供標準 timezone 類別
timedelta = _timedelta    # 向後相容：提供標準 timedelta 類別

# 台灣時區常數（UTC+8）
# 用於所有時間相關的計算和顯示
TW_TZ = _timezone(_timedelta(hours=8))

# =============================================================================
# 2️⃣ 專案路徑設定
# =============================================================================
# 專案根目錄：從環境變數或自動偵測
# 優先使用環境變數 PROJECT_ROOT，如果沒有則自動計算
PROJECT_ROOT = os.environ.get("PROJECT_ROOT")
if not PROJECT_ROOT:
    # 自動計算專案根目錄（config.py 的上一層目錄）
    # 因為 config.py 在專案根目錄下，所以只需要上一層
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# 主要資料夾路徑
DBS_DIR = os.path.join(PROJECT_ROOT, "dbs")      # 資料庫檔案目錄
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")    # 日誌檔案目錄
DATA_DIR = os.path.join(PROJECT_ROOT, "data")    # 一般資料目錄
BG_DIR = os.path.join(DATA_DIR, "backgrounds")   # 背景圖片目錄
FONTS_DIR = os.path.join(PROJECT_ROOT, "fonts")  # 字體檔案目錄

# 自動建立必要的目錄結構
# exist_ok=True 表示如果目錄已存在則不報錯
os.makedirs(DBS_DIR, exist_ok=True)    # 確保資料庫目錄存在
os.makedirs(LOGS_DIR, exist_ok=True)   # 確保日誌目錄存在
os.makedirs(DATA_DIR, exist_ok=True)   # 確保資料目錄存在
os.makedirs(BG_DIR, exist_ok=True)     # 確保背景圖片目錄存在
os.makedirs(FONTS_DIR, exist_ok=True)  # 確保字體目錄存在

# =============================================================================
# 3️⃣ 資料庫檔案路徑
# =============================================================================
# 所有資料庫檔案都存放在 dbs/ 目錄下
# 使用 SQLite 資料庫，檔案格式為 .db

# 訊息相關資料庫
MESSAGE_DB_PATH = os.path.join(DBS_DIR, "message.db")    # 訊息記錄資料庫

# 歡迎系統資料庫
WELCOME_DB_PATH = os.path.join(DBS_DIR, "welcome.db")    # 歡迎設定資料庫

# =============================================================================
# 4️⃣ 日誌檔案路徑
# =============================================================================
# 所有日誌檔案都存放在 logs/ 目錄下
# 每個功能模組都有獨立的日誌檔案

# 訊息監聽器日誌
MESSAGE_LOG_PATH = os.path.join(LOGS_DIR, "message_listener.log")

# 歡迎系統日誌
WELCOME_LOG_PATH = os.path.join(LOGS_DIR, "welcome.log")

# 資料同步日誌
SYNC_DATA_LOG_PATH = os.path.join(LOGS_DIR, "sync_data.log")

# =============================================================================
# 5️⃣ 資源檔案路徑
# =============================================================================
# 歡迎系統相關資源

# 背景圖片目錄（用於歡迎圖片生成）
WELCOME_BG_DIR = BG_DIR

# 字體檔案目錄
WELCOME_FONTS_DIR = FONTS_DIR

# 預設字體檔案（繁體中文支援）
# NotoSansCJKtc-Regular.otf 是 Google 的思源黑體，支援繁體中文
WELCOME_DEFAULT_FONT = os.path.join(FONTS_DIR, "NotoSansCJKtc-Regular.otf")

# =============================================================================
# 6️⃣ 活躍度系統配置
# =============================================================================
# 活躍度系統用於追蹤和獎勵伺服器成員的活動參與度
# 系統會根據成員的訊息活動計算活躍度分數

# 資料庫路徑
ACTIVITY_DB_PATH = os.path.join(DBS_DIR, "activity.db")  # 活躍度資料庫

# 分數計算參數
ACTIVITY_GAIN = 0.5              # 每則訊息獲得的活躍度分數
ACTIVITY_COOLDOWN = 60           # 同一使用者的冷卻時間（秒）
                                 # 在此時間內重複發送訊息不會重複計分

# 分數限制
ACTIVITY_MAX_SCORE = 100         # 活躍度分數上限

# 分數衰減設定
ACTIVITY_DECAY_AFTER = 24 * 3600 # 分數開始衰減的時間（秒）
                                 # 24小時後開始衰減

ACTIVITY_DECAY_PER_H = ACTIVITY_MAX_SCORE / 24   # 每小時衰減的分數
                                                 # 100分 / 24小時 = 4.17分/小時

# =============================================================================
# 7️⃣ 活躍度進度條視覺設定
# =============================================================================
# 用於生成活躍度排行榜的圖片設定

# 進度條尺寸
ACT_BAR_WIDTH = 400              # 進度條寬度（像素）
ACT_BAR_HEIGHT = 40              # 進度條高度（像素）

# 進度條顏色（RGBA 格式）
ACT_BAR_BG = (54, 57, 63, 255)      # 背景色：Discord 深色主題
ACT_BAR_FILL = (0, 200, 255, 255)   # 填充色：青藍色
ACT_BAR_BORDER = (255, 255, 255, 255)  # 邊框色：白色

# 自動排行榜時間
ACT_REPORT_HOUR = 12             # 每日自動發布排行榜的時間（24小時制）

# =============================================================================
# 8️⃣ 權限檢查工具函數
# =============================================================================
def is_allowed(interaction: discord.Interaction, action: str = "") -> bool:
    """
    檢查用戶是否具有管理伺服器權限
    
    參數：
        interaction (discord.Interaction): Discord 互動物件
        action (str): 可選的動作描述，用於日誌記錄
    
    回傳：
        bool: True 表示有權限，False 表示無權限
    
    檢查條件：
    1. 必須在伺服器內執行（不能是私訊）
    2. 用戶必須擁有「管理伺服器 (Manage Guild)」權限
    
    使用範例：
        if is_allowed(interaction, "同步指令"):
            await sync_commands(interaction)
        else:
            await interaction.response.send_message("權限不足")
    """
    # 檢查是否在伺服器內執行
    if not interaction.guild:
        return False
        
    # 透過 guild 獲取成員對象來檢查權限
    # 這比直接檢查 interaction.user 更準確
    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        # 如果無法獲取成員資訊，視為無權限
        return False
        
    # 檢查是否擁有「管理伺服器」權限
    return member.guild_permissions.manage_guild

# =============================================================================
# 9️⃣ 配置驗證函數
# =============================================================================
def validate_config() -> bool:
    """
    驗證所有配置設定是否正確
    
    回傳：
        bool: True 表示配置正確，False 表示有問題
    
    檢查項目：
    - 必要目錄是否存在
    - 必要檔案是否存在
    - 配置參數是否在合理範圍內
    """
    try:
        # 檢查必要目錄
        required_dirs = [DBS_DIR, LOGS_DIR, DATA_DIR, BG_DIR, FONTS_DIR]
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                print(f"❌ 必要目錄不存在：{dir_path}")
                return False
        
        # 檢查預設字體檔案
        if not os.path.exists(WELCOME_DEFAULT_FONT):
            print(f"⚠️  預設字體檔案不存在：{WELCOME_DEFAULT_FONT}")
            print("   💡 歡迎圖片功能可能無法正常運作")
        
        # 檢查配置參數合理性
        if ACTIVITY_GAIN <= 0:
            print("❌ 活躍度增益必須大於 0")
            return False
        
        if ACTIVITY_COOLDOWN < 0:
            print("❌ 冷卻時間不能為負數")
            return False
        
        if ACTIVITY_MAX_SCORE <= 0:
            print("❌ 最大分數必須大於 0")
            return False
        
        print("✅ 配置驗證通過")
        return True
        
    except Exception as e:
        print(f"❌ 配置驗證失敗：{e}")
        return False

# =============================================================================
# 🔟 配置資訊顯示函數
# =============================================================================
def print_config_info():
    """
    顯示當前配置資訊
    用於除錯和確認設定
    """
    print("=" * 60)
    print("🔧 Discord ADR Bot v1.5 - 配置資訊")
    print("=" * 60)
    
    print(f"📁 專案根目錄：{PROJECT_ROOT}")
    print(f"🗄️  資料庫目錄：{DBS_DIR}")
    print(f"📝 日誌目錄：{LOGS_DIR}")
    print(f"📊 資料目錄：{DATA_DIR}")
    print(f"🎨 背景圖片：{BG_DIR}")
    print(f"🔤 字體目錄：{FONTS_DIR}")
    
    print("\n📊 活躍度系統設定：")
    print(f"   • 每則訊息分數：{ACTIVITY_GAIN}")
    print(f"   • 冷卻時間：{ACTIVITY_COOLDOWN} 秒")
    print(f"   • 最大分數：{ACTIVITY_MAX_SCORE}")
    print(f"   • 衰減開始時間：{ACTIVITY_DECAY_AFTER} 秒")
    print(f"   • 每小時衰減：{ACTIVITY_DECAY_PER_H:.2f} 分")
    
    print("\n🎨 進度條設定：")
    print(f"   • 尺寸：{ACT_BAR_WIDTH} x {ACT_BAR_HEIGHT}")
    print(f"   • 自動排行榜時間：{ACT_REPORT_HOUR}:00")
    
    print("\n🌍 時區設定：")
    print(f"   • 台灣時區：{TW_TZ}")
    
    print("=" * 60)

# =============================================================================
# 主程式執行時的配置初始化
# =============================================================================
if __name__ == "__main__":
    # 當直接執行此檔案時，顯示配置資訊並進行驗證
    print_config_info()
    validate_config()