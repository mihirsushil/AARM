import os, sqlite3
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from shared.models import Market, SignalBundle, TradeDecision

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

def analyze_market(market: Market, signals: SignalBundle) -> TradeDecision:
    prompt = f"""You are a sharp prediction market analyst looking for mispricings.

Market: {market.title}
Source: {market.source}
Current market probability: {market.market_prob:.1%}
Volume: ${market.volume:,.0f}

Signals:
- Sentiment delta: {signals.sentiment_delta:+.2f}  (-1 = very bearish, +1 = very bullish)
- News velocity: {signals.news_velocity} mentions
- Cross-market consensus: {signals.cross_market_avg:.1%}
- Signal confidence: {signals.confidence:.0%}

Respond in EXACTLY this format, nothing else:
MODEL_PROB: [number between 0 and 1]
DIRECTION: [YES or NO or PASS]
EDGE: [model_prob minus market_prob, e.g. 0.18 or -0.05]
REASONING: [2-3 sentences max explaining your view]"""

    response = client.chat.completions.create(
       model="meta/llama-3.1-70b-instruct",
        max_tokens=300,
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