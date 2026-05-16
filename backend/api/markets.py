from fastapi import APIRouter
from backend.memory.store import get_latest_markets
from backend.tools.polymarket import fetch_active_markets

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("")
def list_markets(limit: int = 50):
    """Latest snapshot of each market from the DB."""
    return get_latest_markets(limit=limit)


@router.get("/live")
async def live_markets(limit: int = 20):
    """Fetch live market data directly from Polymarket."""
    markets = await fetch_active_markets(limit=limit)
    return [m.model_dump() for m in markets]
