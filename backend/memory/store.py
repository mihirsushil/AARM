import os
import sqlite3
from datetime import datetime, timezone
from backend.models.schemas import Market, SignalResult, ReasoningLog

DB_PATH = os.getenv("DATABASE_PATH", "aarm.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id   TEXT,
    question    TEXT,
    probability REAL,
    volume      REAL,
    liquidity   REAL,
    category    TEXT,
    source      TEXT,
    captured_at TEXT
);

CREATE TABLE IF NOT EXISTS signal_logs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id          TEXT,
    sentiment_score    REAL,
    narrative_velocity REAL,
    divergence_score   REAL,
    market_score       REAL,
    edge               REAL,
    confidence         REAL,
    estimated_prob     REAL,
    signal_count       INTEGER,
    captured_at        TEXT
);

CREATE TABLE IF NOT EXISTS reasoning_logs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id        TEXT,
    market_question  TEXT,
    market_prob      REAL,
    model_prob       REAL,
    edge             REAL,
    direction        TEXT,
    reasoning        TEXT,
    action_taken     TEXT,
    timestamp        TEXT
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id            TEXT NOT NULL,
    market_question      TEXT,
    side                 TEXT,
    entry_probability    REAL,
    current_probability  REAL,
    stake_usd            REAL,
    pnl                  REAL DEFAULT 0.0,
    status               TEXT DEFAULT 'open',
    edge_at_entry        REAL,
    confidence_at_entry  REAL,
    reasoning            TEXT,
    opened_at            TEXT,
    closed_at            TEXT
);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = sqlite3.connect(DB_PATH)
    c.executescript(_SCHEMA)
    c.commit()
    c.close()


def save_market_snapshot(market: Market):
    c = _conn()
    c.execute("""
        INSERT INTO market_snapshots
            (market_id, question, probability, volume, liquidity, category, source, captured_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market.id, market.question, market.probability,
        market.volume, market.liquidity, market.category,
        market.source, datetime.now(timezone.utc).isoformat(),
    ))
    c.commit()
    c.close()


def save_signal_log(signal: SignalResult):
    c = _conn()
    c.execute("""
        INSERT INTO signal_logs
            (market_id, sentiment_score, narrative_velocity, divergence_score,
             market_score, edge, confidence, estimated_prob, signal_count, captured_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        signal.market_id, signal.sentiment_score, signal.narrative_velocity,
        signal.divergence_score, signal.market_score, signal.edge,
        signal.confidence, signal.estimated_prob, signal.signal_count,
        datetime.now(timezone.utc).isoformat(),
    ))
    c.commit()
    c.close()


def save_reasoning_log(log: ReasoningLog):
    c = _conn()
    c.execute("""
        INSERT INTO reasoning_logs
            (market_id, market_question, market_prob, model_prob, edge,
             direction, reasoning, action_taken, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log.market_id, log.market_question, log.market_prob,
        log.model_prob, log.edge, log.direction, log.reasoning,
        log.action_taken, log.timestamp,
    ))
    c.commit()
    c.close()


def get_latest_markets(limit: int = 50) -> list[dict]:
    """Latest snapshot per market, ordered by captured_at desc."""
    c = _conn()
    rows = c.execute("""
        SELECT m.*
        FROM market_snapshots m
        INNER JOIN (
            SELECT market_id, MAX(captured_at) AS max_at
            FROM market_snapshots
            GROUP BY market_id
        ) latest ON m.market_id = latest.market_id
               AND m.captured_at = latest.max_at
        ORDER BY m.captured_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_signal_logs(market_id: str | None = None, limit: int = 100) -> list[dict]:
    c = _conn()
    if market_id:
        rows = c.execute(
            "SELECT * FROM signal_logs WHERE market_id=? ORDER BY captured_at DESC LIMIT ?",
            (market_id, limit),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM signal_logs ORDER BY captured_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_reasoning_logs(limit: int = 50) -> list[dict]:
    c = _conn()
    rows = c.execute(
        "SELECT * FROM reasoning_logs ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]
