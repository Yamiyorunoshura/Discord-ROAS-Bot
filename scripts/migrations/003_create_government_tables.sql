CREATE TABLE IF NOT EXISTS government_departments (
id INTEGER PRIMARY KEY AUTOINCREMENT,
guild_id INTEGER NOT NULL,
name TEXT NOT NULL,
description TEXT,
head_role_id INTEGER,
head_user_id INTEGER,
level_role_id INTEGER,
level_name TEXT,
account_id TEXT,
status TEXT NOT NULL DEFAULT 'active',
budget_limit REAL DEFAULT 0.0,
created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
created_by INTEGER,
metadata TEXT,
CHECK (status IN ('active', 'inactive', 'dissolved')),
CHECK (budget_limit >= 0.0),
FOREIGN KEY (account_id) REFERENCES economy_accounts(id) ON DELETE SET NULL,
UNIQUE(guild_id, name)
);

CREATE INDEX IF NOT EXISTS idx_gov_dept_guild_id ON government_departments(guild_id);

CREATE INDEX IF NOT EXISTS idx_gov_dept_name ON government_departments(guild_id, name);

CREATE INDEX IF NOT EXISTS idx_gov_dept_head_role ON government_departments(head_role_id);

CREATE INDEX IF NOT EXISTS idx_gov_dept_head_user ON government_departments(head_user_id);

CREATE INDEX IF NOT EXISTS idx_gov_dept_account ON government_departments(account_id);

CREATE INDEX IF NOT EXISTS idx_gov_dept_status ON government_departments(status);

CREATE INDEX IF NOT EXISTS idx_gov_dept_created_by ON government_departments(created_by);

CREATE INDEX IF NOT EXISTS idx_gov_dept_updated_at ON government_departments(updated_at);

CREATE TABLE IF NOT EXISTS government_members (
id INTEGER PRIMARY KEY AUTOINCREMENT,
guild_id INTEGER NOT NULL,
user_id INTEGER NOT NULL,
department_id INTEGER,
position_name TEXT NOT NULL,
position_level INTEGER NOT NULL DEFAULT 1,
role_id INTEGER,
appointed_at TIMESTAMP NOT NULL,
appointed_by INTEGER NOT NULL,
term_start_date DATE,
term_end_date DATE,
status TEXT NOT NULL DEFAULT 'active',
resignation_reason TEXT,
dismissed_reason TEXT,
created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
CHECK (status IN ('active', 'suspended', 'resigned', 'dismissed')),
CHECK (position_level > 0),
CHECK (term_end_date IS NULL OR term_end_date > term_start_date),
FOREIGN KEY (department_id) REFERENCES government_departments(id) ON DELETE CASCADE,
UNIQUE(guild_id, user_id, department_id)
);

CREATE INDEX IF NOT EXISTS idx_gov_members_guild_id ON government_members(guild_id);

CREATE INDEX IF NOT EXISTS idx_gov_members_user_id ON government_members(user_id);

CREATE INDEX IF NOT EXISTS idx_gov_members_department_id ON government_members(department_id);

CREATE INDEX IF NOT EXISTS idx_gov_members_position_level ON government_members(position_level);

CREATE INDEX IF NOT EXISTS idx_gov_members_status ON government_members(status);

CREATE INDEX IF NOT EXISTS idx_gov_members_appointed_by ON government_members(appointed_by);

CREATE INDEX IF NOT EXISTS idx_gov_members_term ON government_members(term_start_date, term_end_date);

CREATE INDEX IF NOT EXISTS idx_gov_members_guild_user ON government_members(guild_id, user_id);

CREATE TABLE IF NOT EXISTS government_resolutions (
id INTEGER PRIMARY KEY AUTOINCREMENT,
guild_id INTEGER NOT NULL,
title TEXT NOT NULL,
description TEXT NOT NULL,
resolution_type TEXT NOT NULL,
department_id INTEGER,
proposed_by INTEGER NOT NULL,
proposed_at TIMESTAMP NOT NULL,
voting_start_time TIMESTAMP,
voting_end_time TIMESTAMP,
status TEXT NOT NULL DEFAULT 'draft',
approval_threshold REAL NOT NULL DEFAULT 0.5,
votes_for INTEGER NOT NULL DEFAULT 0,
votes_against INTEGER NOT NULL DEFAULT 0,
votes_abstain INTEGER NOT NULL DEFAULT 0,
implemented_at TIMESTAMP,
implemented_by INTEGER,
metadata TEXT,
CHECK (resolution_type IN ('policy', 'budget', 'appointment', 'disciplinary')),
CHECK (status IN ('draft', 'voting', 'approved', 'rejected', 'implemented')),
CHECK (approval_threshold > 0 AND approval_threshold <= 1),
CHECK (votes_for >= 0 AND votes_against >= 0 AND votes_abstain >= 0),
CHECK (voting_end_time IS NULL OR voting_end_time > voting_start_time),
FOREIGN KEY (department_id) REFERENCES government_departments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_gov_resolutions_guild_id ON government_resolutions(guild_id);

CREATE INDEX IF NOT EXISTS idx_gov_resolutions_type ON government_resolutions(resolution_type);

CREATE INDEX IF NOT EXISTS idx_gov_resolutions_department_id ON government_resolutions(department_id);

CREATE INDEX IF NOT EXISTS idx_gov_resolutions_proposed_by ON government_resolutions(proposed_by);

CREATE INDEX IF NOT EXISTS idx_gov_resolutions_status ON government_resolutions(status);

CREATE INDEX IF NOT EXISTS idx_gov_resolutions_voting_period ON government_resolutions(voting_start_time, voting_end_time);

CREATE INDEX IF NOT EXISTS idx_gov_resolutions_proposed_at ON government_resolutions(proposed_at);

CREATE TABLE IF NOT EXISTS government_votes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
resolution_id INTEGER NOT NULL,
user_id INTEGER NOT NULL,
vote_choice TEXT NOT NULL,
vote_weight REAL NOT NULL DEFAULT 1.0,
voted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
comment TEXT,
is_anonymous INTEGER NOT NULL DEFAULT 0,
CHECK (vote_choice IN ('for', 'against', 'abstain')),
CHECK (vote_weight > 0),
CHECK (is_anonymous IN (0, 1)),
FOREIGN KEY (resolution_id) REFERENCES government_resolutions(id) ON DELETE CASCADE,
UNIQUE(resolution_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_gov_votes_resolution_id ON government_votes(resolution_id);

CREATE INDEX IF NOT EXISTS idx_gov_votes_user_id ON government_votes(user_id);

CREATE INDEX IF NOT EXISTS idx_gov_votes_choice ON government_votes(vote_choice);

CREATE INDEX IF NOT EXISTS idx_gov_votes_voted_at ON government_votes(voted_at);

CREATE INDEX IF NOT EXISTS idx_gov_votes_anonymous ON government_votes(is_anonymous);

CREATE TABLE IF NOT EXISTS government_audit_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
guild_id INTEGER NOT NULL,
operation TEXT NOT NULL,
target_type TEXT NOT NULL,
target_id TEXT NOT NULL,
user_id INTEGER,
old_values TEXT,
new_values TEXT,
created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
success INTEGER NOT NULL DEFAULT 1,
error_message TEXT,
ip_address TEXT,
user_agent TEXT,
CHECK (success IN (0, 1)),
CHECK (target_type IN ('department', 'member', 'resolution', 'vote', 'config'))
);

CREATE INDEX IF NOT EXISTS idx_gov_audit_log_guild_id ON government_audit_log(guild_id);

CREATE INDEX IF NOT EXISTS idx_gov_audit_log_operation ON government_audit_log(operation);

CREATE INDEX IF NOT EXISTS idx_gov_audit_log_target ON government_audit_log(target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_gov_audit_log_user_id ON government_audit_log(user_id);

CREATE INDEX IF NOT EXISTS idx_gov_audit_log_created_at ON government_audit_log(created_at);

CREATE INDEX IF NOT EXISTS idx_gov_audit_log_success ON government_audit_log(success);

CREATE TRIGGER IF NOT EXISTS update_government_departments_timestamp
AFTER UPDATE ON government_departments
FOR EACH ROW
BEGIN
UPDATE government_departments
SET updated_at = CURRENT_TIMESTAMP
WHERE id = NEW.id;

END;

CREATE TRIGGER IF NOT EXISTS update_government_members_timestamp
AFTER UPDATE ON government_members
FOR EACH ROW
BEGIN
UPDATE government_members
SET updated_at = CURRENT_TIMESTAMP
WHERE id = NEW.id;

END;

CREATE TRIGGER IF NOT EXISTS update_resolution_vote_counts
AFTER INSERT ON government_votes
FOR EACH ROW
BEGIN
UPDATE government_resolutions
SET
votes_for = (SELECT SUM(CASE WHEN vote_choice = 'for' THEN vote_weight ELSE 0 END) FROM government_votes WHERE resolution_id = NEW.resolution_id),
votes_against = (SELECT SUM(CASE WHEN vote_choice = 'against' THEN vote_weight ELSE 0 END) FROM government_votes WHERE resolution_id = NEW.resolution_id),
votes_abstain = (SELECT SUM(CASE WHEN vote_choice = 'abstain' THEN vote_weight ELSE 0 END) FROM government_votes WHERE resolution_id = NEW.resolution_id)
WHERE id = NEW.resolution_id;

END;

CREATE TRIGGER IF NOT EXISTS update_resolution_vote_counts_on_update
AFTER UPDATE ON government_votes
FOR EACH ROW
BEGIN
UPDATE government_resolutions
SET
votes_for = (SELECT SUM(CASE WHEN vote_choice = 'for' THEN vote_weight ELSE 0 END) FROM government_votes WHERE resolution_id = NEW.resolution_id),
votes_against = (SELECT SUM(CASE WHEN vote_choice = 'against' THEN vote_weight ELSE 0 END) FROM government_votes WHERE resolution_id = NEW.resolution_id),
votes_abstain = (SELECT SUM(CASE WHEN vote_choice = 'abstain' THEN vote_weight ELSE 0 END) FROM government_votes WHERE resolution_id = NEW.resolution_id)
WHERE id = NEW.resolution_id;

END;

CREATE VIEW IF NOT EXISTS active_government_members AS
SELECT
gm.*,
gd.name as department_name,
gd.status as department_status
FROM government_members gm
LEFT JOIN government_departments gd ON gm.department_id = gd.id
WHERE gm.status = 'active'
AND (gd.status = 'active' OR gd.status IS NULL);

CREATE VIEW IF NOT EXISTS department_statistics AS
SELECT
gd.id,
gd.guild_id,
gd.name,
gd.status,
gd.budget_limit,
COUNT(gm.id) as member_count,
COUNT(CASE WHEN gm.status = 'active' THEN 1 END) as active_member_count,
MAX(gm.position_level) as highest_position_level,
gd.created_at,
gd.updated_at
FROM government_departments gd
LEFT JOIN government_members gm ON gd.id = gm.department_id
GROUP BY gd.id, gd.guild_id, gd.name, gd.status, gd.budget_limit, gd.created_at, gd.updated_at;

CREATE VIEW IF NOT EXISTS resolution_statistics AS
SELECT
guild_id,
COUNT(*) as total_resolutions,
COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_resolutions,
COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_resolutions,
COUNT(CASE WHEN status = 'voting' THEN 1 END) as voting_resolutions,
COUNT(CASE WHEN status = 'implemented' THEN 1 END) as implemented_resolutions,
AVG(CASE WHEN status IN ('approved', 'rejected') THEN votes_for * 1.0 / (votes_for + votes_against) END) as avg_approval_rate
FROM government_resolutions
GROUP BY guild_id;

SELECT name FROM sqlite_master
WHERE type='table' AND name LIKE 'government_%';

SELECT name FROM sqlite_master
WHERE type='index' AND name LIKE 'idx_gov_%';

SELECT name FROM sqlite_master
WHERE type='trigger' AND (name LIKE '%government%' OR name LIKE '%resolution%');

SELECT name FROM sqlite_master
WHERE type='view' AND (name LIKE '%government%' OR name LIKE '%department%' OR name LIKE '%resolution%');

SELECT 'economy_compatibility' as check_name,
CASE WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE name = 'economy_accounts')
THEN 'PASS'
ELSE 'FAIL'
END as result;

SELECT 'core_system_compatibility' as check_name,
CASE WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE name = 'system_config')
THEN 'PASS'
ELSE 'FAIL'
END as result;