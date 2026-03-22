-- FinAgent Database Initialization
-- Run once on project setup: sqlite3 data/finagent.db < scripts/init_db.sql

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- =============================================
-- TRADE HISTORY
-- =============================================
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    position_id TEXT,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    hold_time_hours REAL,
    market_type TEXT NOT NULL, -- sports | prediction | stocks | options | dfs | crypto
    platform TEXT NOT NULL,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL,
    exit_price REAL,
    size_usd REAL NOT NULL,
    gross_pnl REAL,
    fees REAL DEFAULT 0,
    net_pnl REAL,
    roi_pct REAL,
    close_reason TEXT, -- stop_loss | take_profit | manual | expiry | strategy_exit
    edge_estimate_at_open REAL,
    edge_realized REAL,
    risk_manager_approval_id TEXT,
    dry_run INTEGER DEFAULT 1, -- 1=true, 0=false
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- =============================================
-- OPEN POSITIONS (snapshot — also tracked in JSON)
-- =============================================
CREATE TABLE IF NOT EXISTS open_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id TEXT UNIQUE NOT NULL,
    opened_at TEXT NOT NULL,
    market_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL,
    entry_cost REAL NOT NULL,
    current_price REAL,
    current_value REAL,
    current_pnl REAL,
    stop_loss REAL,
    take_profit REAL,
    expiry_datetime TEXT,
    status TEXT DEFAULT 'open',
    risk_manager_approval_id TEXT,
    edge_estimate REAL,
    dry_run INTEGER DEFAULT 1,
    last_updated TEXT DEFAULT (datetime('now'))
);

-- =============================================
-- STRATEGY PERFORMANCE
-- =============================================
CREATE TABLE IF NOT EXISTS strategy_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    market_type TEXT NOT NULL,
    n_bets INTEGER DEFAULT 0,
    n_wins INTEGER DEFAULT 0,
    n_losses INTEGER DEFAULT 0,
    win_rate REAL,
    total_wagered REAL DEFAULT 0,
    total_pnl REAL DEFAULT 0,
    roi REAL,
    avg_edge_estimated REAL,
    avg_edge_realized REAL,
    edge_realization_rate REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- =============================================
-- MODEL CALIBRATION
-- =============================================
CREATE TABLE IF NOT EXISTS model_calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    model_name TEXT NOT NULL,
    market_type TEXT NOT NULL,
    n_predictions INTEGER,
    brier_score REAL,
    log_loss REAL,
    mean_calibration_error REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- =============================================
-- DAILY RISK REPORTS
-- =============================================
CREATE TABLE IF NOT EXISTS daily_risk_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT UNIQUE NOT NULL,
    gross_pnl REAL DEFAULT 0,
    net_pnl REAL DEFAULT 0,
    fees_paid REAL DEFAULT 0,
    daily_limit_used_pct REAL DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate REAL,
    largest_win REAL DEFAULT 0,
    largest_loss REAL DEFAULT 0,
    max_open_positions INTEGER DEFAULT 0,
    tilt_signals_fired INTEGER DEFAULT 0,
    hard_stops_hit INTEGER DEFAULT 0,
    report_json TEXT, -- full JSON report stored here
    created_at TEXT DEFAULT (datetime('now'))
);

-- =============================================
-- ALERTS LOG
-- =============================================
CREATE TABLE IF NOT EXISTS alerts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT UNIQUE,
    fired_at TEXT DEFAULT (datetime('now')),
    severity TEXT NOT NULL, -- CRITICAL | WARNING | INFO
    alert_type TEXT NOT NULL,
    position_id TEXT,
    instrument TEXT,
    message TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0,
    acknowledged_at TEXT
);

-- =============================================
-- OPPORTUNITY LOG (everything MARKET_RESEARCHER surfaces)
-- =============================================
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id TEXT UNIQUE,
    surfaced_at TEXT DEFAULT (datetime('now')),
    market_type TEXT,
    platform TEXT,
    instrument TEXT,
    edge_estimate REAL,
    composite_score REAL,
    data_analyst_validated INTEGER DEFAULT 0,
    risk_manager_decision TEXT, -- approved | rejected | conditional
    executed INTEGER DEFAULT 0,
    trade_id TEXT, -- FK to trades if executed
    notes TEXT
);

-- =============================================
-- INDEXES
-- =============================================
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades(opened_at);
CREATE INDEX IF NOT EXISTS idx_trades_market_type ON trades(market_type);
CREATE INDEX IF NOT EXISTS idx_trades_platform ON trades(platform);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_date ON strategy_performance(date);
CREATE INDEX IF NOT EXISTS idx_alerts_fired_at ON alerts_log(fired_at);
CREATE INDEX IF NOT EXISTS idx_opportunities_surfaced ON opportunities(surfaced_at);

-- =============================================
-- VIEWS
-- =============================================

-- Rolling 7-day P&L by market type
CREATE VIEW IF NOT EXISTS v_weekly_pnl AS
SELECT
    market_type,
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(net_pnl), 2) as net_pnl,
    ROUND(SUM(size_usd), 2) as total_wagered,
    ROUND(SUM(net_pnl) / NULLIF(SUM(size_usd), 0) * 100, 2) as roi_pct
FROM trades
WHERE closed_at >= datetime('now', '-7 days')
  AND dry_run = 0
GROUP BY market_type;

-- Today's summary
CREATE VIEW IF NOT EXISTS v_today_summary AS
SELECT
    COUNT(*) as total_trades,
    ROUND(SUM(net_pnl), 2) as net_pnl,
    ROUND(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END), 2) as gross_wins,
    ROUND(SUM(CASE WHEN net_pnl < 0 THEN net_pnl ELSE 0 END), 2) as gross_losses,
    MAX(net_pnl) as best_trade,
    MIN(net_pnl) as worst_trade
FROM trades
WHERE date(closed_at) = date('now')
  AND dry_run = 0;

SELECT 'Database initialized successfully.' as status;
