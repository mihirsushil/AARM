from fastapi import APIRouter
from backend.memory.store import get_reasoning_logs

router = APIRouter(prefix="/reasoning", tags=["reasoning"])


@router.get("")
def list_reasoning(limit: int = 50):
    return get_reasoning_logs(limit=limit)
