import os, sqlite3
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import httpx
from shared.models import Market, SignalBundle, TradeDecision

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

# ── Step 1: Trust filter ──────────────────────────────────────────────────────

def is_signal_trustworthy(text: str) -> bool:
    """Uses NVIDIA content safety to check if a signal is reliable."""
    try:
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-content-safety",
            max_tokens=50,
            messages=[{"role": "user", "content": text}]
        )
        result = response.choices[0].message.content.lower()
        return "unsafe" not in result and "toxic" not in result
    except Exception:
        return True  # if filter fails, don't block the signal


# ── Step 2: Cross-market search ───────────────────────────────────────────────

def get_embedding(text: str, input_type: str = "query") -> list:
    """Converts text to a vector using NVIDIA embed model."""
    response = client.embeddings.create(
        model="nvidia/llama-nemotron-embed-1b-v2",
        input=text,
        extra_body={"input_type": input_type, "truncate": "END"}
    )
    return response.data[0].embedding


def cosine_similarity(a: list, b: list) -> float:
    """How similar are two embeddings? 1.0 = identical, 0.0 = unrelated."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x ** 2 for x in a) ** 0.5
    mag_b = sum(x ** 2 for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_related_markets(query: str, top_k: int = 3) -> list:
    query_embedding = get_embedding(query, input_type="query")
    
    all_markets = []
    
    # try Manifold
    try:
        resp = httpx.get(
            "https://manifold.markets/api/v0/markets",
            params={"limit": 50, "sort": "liquidity"},
            timeout=15
        )
        if resp.status_code == 200 and resp.text:
            for m in resp.json():
                if not m.get("isResolved") and m.get("question"):
                    all_markets.append({
                        "title": m["question"],
                        "probability": m.get("probability", 0.5),
                        "source": "manifold",
                        "volume": m.get("volume", 0)
                    })
    except Exception as e:
        print(f"Manifold fetch failed: {e}")

    
    # try Polymarket
    try:
        resp = httpx.get(
            "https://gamma-api.polymarket.com/markets",
            params={"active": "true", "limit": 50},
            timeout=15
        )
        if resp.status_code == 200 and resp.text:
            for m in resp.json():
                if m.get("question"):
                    try:
                        prices = m.get("outcomePrices", ["0.5"])
                        if isinstance(prices, str):
                            import json
                            prices = json.loads(prices)
                        prob = float(prices[0]) if prices else 0.5
                    except Exception:
                        prob = 0.5
                    all_markets.append({
                        "title": m["question"],
                        "probability": prob,
                        "source": "polymarket",
                        "volume": float(m.get("volume", 0) or 0)
                    })
    except Exception as e:
        print(f"Polymarket fetch failed: {e}")

    if not all_markets:
        print("No markets fetched from any source")
        return []

    print(f"Fetched {len(all_markets)} markets, scoring similarity...")

    scored = []
    for m in all_markets:
        try:
            emb = get_embedding(m["title"], input_type="passage")
            score = cosine_similarity(query_embedding, emb)
            m["similarity"] = score
            scored.append(m)
        except Exception:
            continue

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]
               


# ── Step 3: Final reasoning ───────────────────────────────────────────────────

def analyze_market(market: Market, signals: SignalBundle) -> TradeDecision:
    print(f"\n[1/3] Checking signal trustworthiness...")
    signal_safe = is_signal_trustworthy(market.title)

    if not signal_safe:
        print("Signal flagged as untrustworthy — skipping.")
        return TradeDecision(
            market_id=market.id,
            edge=0.0,
            direction="PASS",
            stake_pct=0.0,
            reasoning="Signal flagged as untrustworthy by NVIDIA content safety filter.",
            model_prob=market.market_prob
        )

    print(f"[2/3] Searching for related markets...")
    related = find_related_markets(market.title)

    related_text = ""
    if related:
        related_text = "\nRelated markets found across platforms:\n"
        for r in related:
            related_text += (
                f"- \"{r['title']}\" → {r['probability']:.0%} "
                f"(source: {r['source']}, volume: ${r['volume']:,.0f}, "
                f"similarity: {r['similarity']:.2f})\n"
            )
    else:
        related_text = "\nNo related markets found.\n"

    print(f"[3/3] Running Mistral Nemotron analysis...")

    prompt = f"""You are a sharp prediction market analyst looking for mispricings.

Market to analyze:
Title: {market.title}
Source: {market.source}
Current market probability: {market.market_prob:.1%}
Volume: ${market.volume:,.0f}

Live signals:
- Sentiment delta: {signals.sentiment_delta:+.2f}  (-1 = very bearish, +1 = very bullish)
- News velocity: {signals.news_velocity} mentions
- Cross-market consensus: {signals.cross_market_avg:.1%}
- Signal confidence: {signals.confidence:.0%}
{related_text}
Based on ALL of the above — the market price, signals, and related markets —
estimate the true probability and identify any mispricing.

Respond in EXACTLY this format, nothing else:
MODEL_PROB: [number between 0 and 1]
DIRECTION: [YES or NO or PASS]
EDGE: [model_prob minus market_prob, e.g. 0.18 or -0.05]
REASONING: [2-3 sentences explaining your view, referencing the related markets]"""

    response = client.chat.completions.create(
        model="mistralai/mistral-nemotron",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content.strip()

    parsed = {}
    for line in text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            parsed[key.strip()] = val.strip()

    model_prob = float(parsed.get("MODEL_PROB", market.market_prob))
    edge = float(parsed.get("EDGE", "0"))
    direction = parsed.get("DIRECTION", "PASS")
    reasoning = parsed.get("REASONING", "No reasoning provided")

    if direction != "PASS" and abs(edge) > 0.08:
        raw_kelly = abs(edge) / (1 - market.market_prob + abs(edge))
        stake = min(raw_kelly * 0.25, 0.05)
    else:
        stake = 0.0
        direction = "PASS"

    return TradeDecision(
        market_id=market.id,
        edge=edge,
        direction=direction,
        stake_pct=stake,
        reasoning=reasoning,
        model_prob=model_prob
    )


# ── Database ──────────────────────────────────────────────────────────────────

def save_trade(decision: TradeDecision, bankroll: float = 10000.0):
    conn = sqlite3.connect("aarm.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            direction TEXT,
            edge REAL,
            stake_usd REAL,
            model_prob REAL,
            reasoning TEXT,
            timestamp TEXT,
            status TEXT DEFAULT 'open',
            pnl REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        INSERT INTO trades
        (market_id, direction, edge, stake_usd, model_prob, reasoning, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        decision.market_id,
        decision.direction,
        decision.edge,
        bankroll * decision.stake_pct,
        decision.model_prob,
        decision.reasoning,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def get_all_trades():
    conn = sqlite3.connect("aarm.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]