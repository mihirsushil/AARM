import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from backend.models.schemas import Market, SignalResult, PaperTrade, Portfolio

DB_PATH = os.getenv("DATABASE_PATH", "aarm.db")
BANKROLL = float(os.getenv("BANKROLL", "10000"))
MAX_POSITION_PCT = 0.05
MIN_EDGE = float(os.getenv("EDGE_THRESHOLD", "0.08"))
MIN_CONFIDENCE = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _kelly_fraction(edge: float, market_prob: float, direction: str) -> float:
    if direction == "BUY":
        denom = 1.0 - market_prob
    else:
        denom = market_prob
    if denom <= 0:
        return 0.0
    return min(abs(edge) / denom * 0.25, MAX_POSITION_PCT)


def should_trade(signal: SignalResult) -> tuple[bool, str]:
    """Returns (trade, direction). Direction is BUY or SELL."""
    if signal.confidence < MIN_CONFIDENCE or abs(signal.edge) < MIN_EDGE:
        return False, "PASS"
    direction = "BUY" if signal.edge > 0 else "SELL"
    return True, direction


def is_already_trading(market_id: str) -> bool:
    c = _conn()
    row = c.execute(
        "SELECT id FROM paper_trades WHERE market_id=? AND status='open'",
        (market_id,),
    ).fetchone()
    c.close()
    return row is not None


def open_trade(
    market: Market,
    signal: SignalResult,
    direction: str,
    reasoning: str,
) -> Optional[PaperTrade]:
    fraction = _kelly_fraction(signal.edge, market.probability, direction)
    stake_usd = BANKROLL * fraction
    if stake_usd < 1.0:
        return None

    now = datetime.now(timezone.utc).isoformat()
    c = _conn()
    c.execute("""
        INSERT INTO paper_trades
            (market_id, market_question, side, entry_probability, current_probability,
             stake_usd, pnl, status, edge_at_entry, confidence_at_entry, reasoning, opened_at)
        VALUES (?, ?, ?, ?, ?, ?, 0.0, 'open', ?, ?, ?, ?)
    """, (
        market.id, market.question, direction,
        market.probability, market.probability,
        stake_usd, signal.edge, signal.confidence, reasoning, now,
    ))
    c.commit()
    trade_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.close()

    return PaperTrade(
        id=trade_id,
        market_id=market.id,
        market_question=market.question,
        side=direction,
        entry_probability=market.probability,
        current_probability=market.probability,
        stake_usd=round(stake_usd, 2),
        pnl=0.0,
        status="open",
        edge_at_entry=signal.edge,
        confidence_at_entry=signal.confidence,
        reasoning=reasoning,
        opened_at=now,
    )


def update_open_trades(current_markets: list[Market]):
    """Recompute mark-to-market PnL for every open trade."""
    market_map = {m.id: m for m in current_markets}
    c = _conn()
    rows = c.execute(
        "SELECT * FROM paper_trades WHERE status='open'"
    ).fetchall()

    for row in rows:
        market = market_map.get(row["market_id"])
        if not market:
            continue
        current = market.probability
        entry = row["entry_probability"]
        stake = row["stake_usd"]
        side = row["side"]

        if side == "BUY":
            pnl = stake * (current - entry) / entry if entry > 0 else 0.0
        else:
            pnl = stake * (entry - current) / (1.0 - entry) if entry < 1.0 else 0.0

        c.execute(
            "UPDATE paper_trades SET current_probability=?, pnl=? WHERE id=?",
            (current, round(pnl, 4), row["id"]),
        )

    c.commit()
    c.close()


def get_all_trades() -> list[dict]:
    c = _conn()
    rows = c.execute(
        "SELECT * FROM paper_trades ORDER BY opened_at DESC"
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_portfolio() -> Portfolio:
    c = _conn()
    rows = c.execute("SELECT * FROM paper_trades").fetchall()
    c.close()

    open_trades = [r for r in rows if r["status"] == "open"]
    closed_trades = [r for r in rows if r["status"] == "closed"]

    deployed = sum(r["stake_usd"] for r in open_trades)
    unrealized = sum(r["pnl"] for r in open_trades)
    realized = sum(r["pnl"] for r in closed_trades)
    wins = sum(1 for r in closed_trades if r["pnl"] > 0)
    losses = sum(1 for r in closed_trades if r["pnl"] <= 0)

    return Portfolio(
        bankroll=BANKROLL,
        deployed=round(deployed, 2),
        available=round(max(0.0, BANKROLL - deployed), 2),
        total_pnl=round(unrealized + realized, 2),
        unrealized_pnl=round(unrealized, 2),
        realized_pnl=round(realized, 2),
        win_count=wins,
        loss_count=losses,
        win_rate=round(wins / max(1, wins + losses), 4),
        open_trades=len(open_trades),
        total_trades=len(rows),
    )
