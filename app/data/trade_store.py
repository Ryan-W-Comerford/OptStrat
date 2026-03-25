"""
TradeStore — SQLite persistence for straddle/strangle candidates.

Status lifecycle:
  pending      → candidate found by scanner, awaiting earnings
  resolved_win → post-earnings IV expanded from entry to exit (1 day before earnings)
  resolved_loss→ IV contracted or flat from entry to exit
  unresolvable → no IV or cost data available
  expired      → options expired with no resolution
"""
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path


class TradeStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker                  TEXT NOT NULL,
                    strategy                TEXT NOT NULL DEFAULT 'longStraddleEarnings',
                    scan_date               TEXT NOT NULL,
                    earnings_date           TEXT NOT NULL,
                    days_to_earnings        INTEGER,
                    status                  TEXT NOT NULL DEFAULT 'pending',

                    -- Greeks & IV at scan time
                    iv_rank                 REAL,
                    vega_theta_ratio        REAL,
                    current_iv              REAL,

                    -- Call leg at scan
                    call_symbol             TEXT,
                    call_strike             REAL,
                    call_expiry             TEXT,
                    call_delta              REAL,
                    call_theta              REAL,
                    call_vega               REAL,
                    call_iv                 REAL,
                    call_ask                REAL,
                    call_oi                 INTEGER,

                    -- Put leg at scan
                    put_symbol              TEXT,
                    put_strike              REAL,
                    put_expiry              TEXT,
                    put_delta               REAL,
                    put_theta               REAL,
                    put_vega               REAL,
                    put_iv                  REAL,
                    put_ask                 REAL,
                    put_oi                  INTEGER,

                    -- Entry pricing (day.close mid-price from $29 plan)
                    call_entry_price        REAL,     -- day.close of call at scan
                    put_entry_price         REAL,     -- day.close of put at scan
                    total_cost              REAL,     -- (call + put) * 100
                    stock_price_at_scan     REAL,     -- price when candidate was first found (never changes)
                    stock_price_current     REAL,     -- updated on every sync
                    stock_price_last_sync   TEXT,     -- date of last sync update

                    -- Exit option pricing (populated when on $199 plan)
                    exit_call_price         REAL,
                    exit_put_price          REAL,
                    exit_total_value        REAL,

                    -- Resolution (filled in by sync command)
                    stock_price_at_exit     REAL,
                    actual_move_pct         REAL,
                    breakeven_pct           REAL,
                    pnl_estimate            REAL,
                    iv_at_exit              REAL,
                    pnl_method              TEXT,
                    resolved_date           TEXT,
                    notes                   TEXT,

                    -- Dedup key
                    UNIQUE(ticker, earnings_date, call_symbol, put_symbol)
                )
            """)

    def _migrate(self) -> None:
        """Add new columns to existing DBs without breaking old data."""
        with self._conn() as conn:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
            migrations = [
                ("strategy",              "ALTER TABLE trades ADD COLUMN strategy TEXT NOT NULL DEFAULT 'longStraddleEarnings'"),
                ("iv_at_exit",            "ALTER TABLE trades ADD COLUMN iv_at_exit REAL"),
                ("pnl_method",            "ALTER TABLE trades ADD COLUMN pnl_method TEXT"),
                ("stock_price_current",   "ALTER TABLE trades ADD COLUMN stock_price_current REAL"),
                ("stock_price_last_sync", "ALTER TABLE trades ADD COLUMN stock_price_last_sync TEXT"),
                ("exit_call_price",       "ALTER TABLE trades ADD COLUMN exit_call_price REAL"),
                ("exit_put_price",        "ALTER TABLE trades ADD COLUMN exit_put_price REAL"),
                ("exit_total_value",      "ALTER TABLE trades ADD COLUMN exit_total_value REAL"),
                ("stock_price_at_exit",   "ALTER TABLE trades ADD COLUMN stock_price_at_exit REAL"),
                ("call_entry_price",      "ALTER TABLE trades ADD COLUMN call_entry_price REAL"),
                ("put_entry_price",       "ALTER TABLE trades ADD COLUMN put_entry_price REAL"),
            ]
            for col, sql in migrations:
                if col not in existing:
                    conn.execute(sql)

    def save_candidate(
        self,
        candidate,
        stock_price: float,
        strategy: str = "longStraddleEarnings",
    ) -> bool:
        """Insert candidate. Returns True if inserted, False if duplicate."""
        c = candidate
        current_iv = (c.call.iv + c.put.iv) / 2
        call_entry = c.call.ask   # day.close mid via fallback in massive.py
        put_entry  = c.put.ask
        total_cost = round((call_entry + put_entry) * 100, 2) if (call_entry and put_entry) else c.total_cost
        with self._conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO trades (
                        ticker, strategy, scan_date, earnings_date, days_to_earnings,
                        iv_rank, vega_theta_ratio, current_iv,
                        call_symbol, call_strike, call_expiry, call_delta,
                        call_theta, call_vega, call_iv, call_ask, call_oi,
                        put_symbol, put_strike, put_expiry, put_delta,
                        put_theta, put_vega, put_iv, put_ask, put_oi,
                        call_entry_price, put_entry_price,
                        total_cost, stock_price_at_scan, stock_price_current, stock_price_last_sync
                    ) VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    c.ticker, strategy, str(date.today()), str(c.earnings_date), c.days_to_earnings,
                    c.iv_rank, c.vega_theta_ratio, current_iv,
                    c.call.symbol, c.call.strike, str(c.call.expiration), c.call.delta,
                    c.call.theta, c.call.vega, c.call.iv, c.call.ask, c.call.open_interest,
                    c.put.symbol, c.put.strike, str(c.put.expiration), c.put.delta,
                    c.put.theta, c.put.vega, c.put.iv, c.put.ask, c.put.open_interest,
                    call_entry, put_entry,
                    total_cost, stock_price, stock_price, str(date.today()),
                ))
                return True
            except sqlite3.IntegrityError:
                return False  # duplicate

    def update_current_price(self, trade_id: int, current_price: float) -> None:
        """Update the current stock price for a pending trade (called on every sync)."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE trades SET
                    stock_price_current   = ?,
                    stock_price_last_sync = ?
                WHERE id = ?
            """, (current_price, str(date.today()), trade_id))

    def get_pending(self) -> list[sqlite3.Row]:
        """Return all trades still pending resolution."""
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM trades WHERE status = 'pending' ORDER BY earnings_date"
            ).fetchall()

    def sync_trade(
        self,
        trade_id: int,
        iv_at_entry: float,
        iv_at_exit: float,
        total_cost: float,
        stock_price_at_exit: float,
        stock_price_at_scan: float,
        exit_call_price: float = 0.0,
        exit_put_price: float = 0.0,
        call_entry_price: float = 0.0,
        put_entry_price: float = 0.0,
    ) -> str:
        """
        Resolve a pending trade.

        Priority order for P&L method:
        1. real_dollar: exit option prices vs entry prices (most accurate)
           pnl = (exit_call + exit_put - entry_call - entry_put) / (entry_call + entry_put) * 100
        2. iv_expansion: % change in realized IV from entry to exit (proxy)
        3. move_vs_breakeven: stock move % vs breakeven % (last resort)
        """
        actual_move_pct = abs(stock_price_at_exit - stock_price_at_scan) / stock_price_at_scan * 100 if stock_price_at_scan else 0

        if exit_call_price > 0 and exit_put_price > 0 and call_entry_price > 0 and put_entry_price > 0:
            # Best method — real dollar P&L from actual option prices
            pnl_method = "real_dollar"
            entry_total = call_entry_price + put_entry_price
            exit_total  = exit_call_price + exit_put_price
            pnl_estimate = (exit_total - entry_total) / entry_total * 100
            dollar_pnl   = (exit_total - entry_total) * 100  # per contract
            status = "resolved_win" if pnl_estimate > 0 else "resolved_loss"
            breakeven_pct = None
            notes = f"${entry_total:.2f} → ${exit_total:.2f} (${dollar_pnl:+.0f}/contract)"

        elif iv_at_entry > 0 and iv_at_exit > 0:
            # Proxy method — IV expansion
            pnl_method = "iv_expansion"
            pnl_estimate = (iv_at_exit - iv_at_entry) / iv_at_entry * 100
            status = "resolved_win" if pnl_estimate > 0 else "resolved_loss"
            breakeven_pct = None
            notes = f"IV {iv_at_entry:.3f} → {iv_at_exit:.3f}"

        elif total_cost > 0 and stock_price_at_scan > 0:
            # Last resort — stock move vs breakeven
            pnl_method = "move_vs_breakeven"
            breakeven_pct = (total_cost / stock_price_at_scan) * 100
            pnl_estimate = actual_move_pct - breakeven_pct
            status = "resolved_win" if pnl_estimate > 0 else "resolved_loss"
            notes = None

        else:
            status = "unresolvable"
            pnl_method = None
            breakeven_pct = None
            pnl_estimate = None
            notes = "No price or IV data available"

        with self._conn() as conn:
            conn.execute("""
                UPDATE trades SET
                    status              = ?,
                    stock_price_at_exit = ?,
                    actual_move_pct     = ?,
                    breakeven_pct       = ?,
                    pnl_estimate        = ?,
                    iv_at_exit          = ?,
                    pnl_method          = ?,
                    exit_call_price     = ?,
                    exit_put_price      = ?,
                    exit_total_value    = ?,
                    resolved_date       = ?,
                    notes               = ?
                WHERE id = ?
            """, (
                status, stock_price_at_exit, actual_move_pct,
                breakeven_pct, pnl_estimate, iv_at_exit,
                pnl_method, exit_call_price or None, exit_put_price or None,
                (exit_call_price + exit_put_price) * 100 if (exit_call_price and exit_put_price) else None,
                str(date.today()), notes,
                trade_id,
            ))
        return status

    def get_all(self) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM trades ORDER BY earnings_date DESC"
            ).fetchall()

    def get_stats(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status='resolved_win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN status='resolved_loss' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN status='unresolvable' THEN 1 ELSE 0 END) as unresolvable,
                    AVG(CASE WHEN status IN ('resolved_win','resolved_loss') THEN pnl_estimate END) as avg_pnl,
                    AVG(CASE WHEN status='resolved_win' THEN pnl_estimate END) as avg_win,
                    AVG(CASE WHEN status='resolved_loss' THEN pnl_estimate END) as avg_loss
                FROM trades
            """).fetchone()
            return dict(rows)