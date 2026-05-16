from fastapi import APIRouter
from backend.memory.store import get_signal_logs

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
def list_signals(market_id: str = None, limit: int = 100):
    return get_signal_logs(market_id=market_id, limit=limit)
