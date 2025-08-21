CREATE TABLE IF NOT EXISTS economy_accounts (
id TEXT PRIMARY KEY,
account_type TEXT NOT NULL,
guild_id INTEGER NOT NULL,
user_id INTEGER,
balance REAL NOT NULL DEFAULT 0.0,
created_at TEXT NOT NULL,
updated_at TEXT NOT NULL,
is_active INTEGER NOT NULL DEFAULT 1,
metadata TEXT,
CHECK (account_type IN ('user', 'government_council', 'government_department')),
CHECK (balance >= 0.0),
CHECK (is_active IN (0, 1)),
CHECK (
(account_type = 'user' AND user_id IS NOT NULL) OR
(account_type IN ('government_council', 'government_department') AND user_id IS NULL)
)
);

CREATE INDEX IF NOT EXISTS idx_economy_accounts_guild_id ON economy_accounts(guild_id);

CREATE INDEX IF NOT EXISTS idx_economy_accounts_user_id ON economy_accounts(user_id);

CREATE INDEX IF NOT EXISTS idx_economy_accounts_type_guild ON economy_accounts(account_type, guild_id);

CREATE INDEX IF NOT EXISTS idx_economy_accounts_active ON economy_accounts(is_active);

CREATE TABLE IF NOT EXISTS economy_transactions (
id INTEGER PRIMARY KEY AUTOINCREMENT,
from_account TEXT,
to_account TEXT,
amount REAL NOT NULL,
transaction_type TEXT NOT NULL,
reason TEXT,
guild_id INTEGER NOT NULL,
created_by INTEGER,
created_at TEXT NOT NULL,
status TEXT NOT NULL DEFAULT 'completed',
reference_id TEXT,
metadata TEXT,
CHECK (amount > 0.0),
CHECK (transaction_type IN ('transfer', 'deposit', 'withdraw', 'reward', 'penalty')),
CHECK (status IN ('pending', 'completed', 'failed', 'cancelled')),
CHECK (
(transaction_type = 'transfer' AND from_account IS NOT NULL AND to_account IS NOT NULL) OR
(transaction_type = 'deposit' AND from_account IS NULL AND to_account IS NOT NULL) OR
(transaction_type = 'withdraw' AND from_account IS NOT NULL AND to_account IS NULL) OR
(transaction_type IN ('reward', 'penalty'))
),
FOREIGN KEY (from_account) REFERENCES economy_accounts(id) ON DELETE SET NULL,
FOREIGN KEY (to_account) REFERENCES economy_accounts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_from_account ON economy_transactions(from_account);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_to_account ON economy_transactions(to_account);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_guild_id ON economy_transactions(guild_id);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_type ON economy_transactions(transaction_type);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_created_at ON economy_transactions(created_at);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_status ON economy_transactions(status);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_created_by ON economy_transactions(created_by);

CREATE TABLE IF NOT EXISTS currency_settings (
guild_id INTEGER PRIMARY KEY,
currency_name TEXT NOT NULL DEFAULT '金幣',
currency_symbol TEXT NOT NULL DEFAULT '💰',
decimal_places INTEGER NOT NULL DEFAULT 2,
min_transfer_amount REAL NOT NULL DEFAULT 1.0,
max_transfer_amount REAL,
daily_transfer_limit REAL,
enable_negative_balance INTEGER NOT NULL DEFAULT 0,
created_at TEXT NOT NULL,
updated_at TEXT NOT NULL,
CHECK (decimal_places >= 0 AND decimal_places <= 8),
CHECK (min_transfer_amount >= 0.0),
CHECK (max_transfer_amount IS NULL OR max_transfer_amount >= min_transfer_amount),
CHECK (daily_transfer_limit IS NULL OR daily_transfer_limit >= 0.0),
CHECK (enable_negative_balance IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_currency_settings_guild_id ON currency_settings(guild_id);

CREATE TABLE IF NOT EXISTS economy_audit_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
operation TEXT NOT NULL,
target_type TEXT NOT NULL,
target_id TEXT NOT NULL,
guild_id INTEGER NOT NULL,
user_id INTEGER,
old_values TEXT,
new_values TEXT,
ip_address TEXT,
user_agent TEXT,
created_at TEXT NOT NULL,
success INTEGER NOT NULL,
error_message TEXT,
CHECK (success IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_economy_audit_log_operation ON economy_audit_log(operation);

CREATE INDEX IF NOT EXISTS idx_economy_audit_log_target ON economy_audit_log(target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_economy_audit_log_guild_id ON economy_audit_log(guild_id);

CREATE INDEX IF NOT EXISTS idx_economy_audit_log_user_id ON economy_audit_log(user_id);

CREATE INDEX IF NOT EXISTS idx_economy_audit_log_created_at ON economy_audit_log(created_at);

SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'economy_%' OR name = 'currency_settings';

SELECT name FROM sqlite_master WHERE type='index' AND (name LIKE 'idx_economy_%' OR name LIKE 'idx_currency_%');