import sqlite3
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from backend.trading.paper_engine import get_all_trades

router = APIRouter(prefix="/trades", tags=["trades"])

DB_PATH = os.getenv("DATABASE_PATH", "aarm.db")


@router.get("")
def list_trades():
    return get_all_trades()


@router.post("/close/{trade_id}")
def close_trade(trade_id: int):
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    row = c.execute(
        "SELECT * FROM paper_trades WHERE id=?", (trade_id,)
    ).fetchone()

    if not row:
        c.close()
        raise HTTPException(status_code=404, detail="Trade not found")
    if row["status"] == "closed":
        c.close()
        raise HTTPException(status_code=400, detail="Trade already closed")

    now = datetime.now(timezone.utc).isoformat()
    c.execute(
        "UPDATE paper_trades SET status='closed', closed_at=? WHERE id=?",
        (now, trade_id),
    )
    c.commit()
    row = c.execute("SELECT * FROM paper_trades WHERE id=?", (trade_id,)).fetchone()
    c.close()
    return dict(row)
