from fastapi import APIRouter
from backend.trading.paper_engine import get_portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
def portfolio():
    return get_portfolio().model_dump()
