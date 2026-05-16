import json
import httpx
from backend.models.schemas import Market

GAMMA_URL = "https://gamma-api.polymarket.com/markets"


async def fetch_active_markets(limit: int = 100) -> list[Market]:
    markets = []
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                GAMMA_URL,
                params={"active": "true", "closed": "false", "limit": limit}
            )
            if resp.status_code != 200:
                print(f"[polymarket] HTTP {resp.status_code}")
                return []

            for m in resp.json():
                if not m.get("question"):
                    continue
                try:
                    prices = m.get("outcomePrices", ["0.5"])
                    if isinstance(prices, str):
                        prices = json.loads(prices)
                    prob = float(prices[0]) if prices else 0.5
                    prob = max(0.01, min(0.99, prob))
                except Exception:
                    prob = 0.5

                markets.append(Market(
                    id=str(m.get("id", "")),
                    question=m.get("question", ""),
                    probability=prob,
                    volume=float(m.get("volume", 0) or 0),
                    liquidity=float(m.get("liquidity", 0) or 0),
                    category=m.get("category", "") or "",
                    slug=m.get("slug"),
                    end_date=m.get("endDate"),
                    description=(m.get("description", "") or "")[:500],
                ))
    except Exception as e:
        print(f"[polymarket] fetch failed: {e}")

    return markets


def fetch_active_markets_sync(limit: int = 100) -> list[Market]:
    """Synchronous version for use outside async contexts."""
    markets = []
    try:
        resp = httpx.get(
            GAMMA_URL,
            params={"active": "true", "closed": "false", "limit": limit},
            timeout=20.0
        )
        if resp.status_code != 200:
            return []

        for m in resp.json():
            if not m.get("question"):
                continue
            try:
                prices = m.get("outcomePrices", ["0.5"])
                if isinstance(prices, str):
                    prices = json.loads(prices)
                prob = float(prices[0]) if prices else 0.5
                prob = max(0.01, min(0.99, prob))
            except Exception:
                prob = 0.5

            markets.append(Market(
                id=str(m.get("id", "")),
                question=m.get("question", ""),
                probability=prob,
                volume=float(m.get("volume", 0) or 0),
                liquidity=float(m.get("liquidity", 0) or 0),
                category=m.get("category", "") or "",
                slug=m.get("slug"),
                end_date=m.get("endDate"),
                description=(m.get("description", "") or "")[:500],
            ))
    except Exception as e:
        print(f"[polymarket] sync fetch failed: {e}")

    return markets
