import asyncio
import os
from datetime import datetime, timezone

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from backend.models.schemas import Market, ReasoningLog, SignalResult
from backend.tools.polymarket import fetch_active_markets
from backend.tools.reddit import fetch_reddit_signals
from backend.signal_processing.scorer import score_market
from backend.trading.paper_engine import (
    should_trade, open_trade, update_open_trades, is_already_trading,
)
from backend.memory.store import (
    init_db, save_market_snapshot, save_signal_log, save_reasoning_log,
)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
TOP_MARKETS = int(os.getenv("TOP_MARKETS_PER_CYCLE", "10"))
EDGE_THRESHOLD = float(os.getenv("EDGE_THRESHOLD", "0.08"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
)


def _run_reasoning(market: Market, signal: SignalResult) -> tuple[float, str, str]:
    """Call Nemotron to reason about a market. Returns (model_prob, reasoning, direction)."""
    prompt = f"""You are an autonomous prediction market analyst hunting for mispricings.

Market: {market.question}
Current market probability: {market.probability:.1%}
Volume: ${market.volume:,.0f}  |  Liquidity: ${market.liquidity:,.0f}

Signal data:
- Sentiment score: {signal.sentiment_score:+.3f}  (-1=very bearish, +1=very bullish)
- Narrative velocity: {signal.narrative_velocity:.3f}  (0=silent, 1=viral)
- Social divergence from market: {signal.divergence_score:+.3f}
- Signal confidence: {signal.confidence:.0%}
- Signal-estimated probability: {signal.estimated_prob:.1%}

Task: Determine whether this market is mispriced relative to true probability.

Respond in EXACTLY this format, no extra text:
MODEL_PROB: [number 0.01–0.99]
DIRECTION: [YES or NO or PASS]
REASONING: [2-3 sentences explaining your view]"""

    try:
        resp = _client.chat.completions.create(
            model="mistralai/mistral-nemotron",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        parsed: dict[str, str] = {}
        for line in text.split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                parsed[k.strip()] = v.strip()

        model_prob = float(parsed.get("MODEL_PROB", market.probability))
        model_prob = max(0.01, min(0.99, model_prob))
        direction = parsed.get("DIRECTION", "PASS").upper()
        reasoning = parsed.get("REASONING", "No reasoning provided.")
        return model_prob, reasoning, direction
    except Exception as e:
        print(f"[agent] reasoning error for {market.id}: {e}")
        return market.probability, "Reasoning unavailable.", "PASS"


async def _run_cycle():
    print(f"\n[loop] ── cycle at {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} ──")

    markets = await fetch_active_markets(limit=100)
    if not markets:
        print("[loop] no markets fetched, skipping")
        return

    print(f"[loop] {len(markets)} markets fetched")

    # Focus on highest-volume markets to keep API costs down
    top = sorted(markets, key=lambda m: m.volume, reverse=True)[:TOP_MARKETS]
    market_map = {m.id: m for m in markets}

    for market in top:
        try:
            save_market_snapshot(market)

            reddit_signals = fetch_reddit_signals(market.question, market.id)
            signal = score_market(market, reddit_signals)
            save_signal_log(signal)

            label = f"edge={signal.edge:+.2f} conf={signal.confidence:.0%}"
            print(f"[loop]   {market.question[:55]:55s} {label}")

            # Skip AI reasoning if signal is too weak — saves API calls
            if abs(signal.edge) < EDGE_THRESHOLD or signal.confidence < CONFIDENCE_THRESHOLD:
                continue

            if is_already_trading(market.id):
                continue

            model_prob, reasoning, llm_dir = _run_reasoning(market, signal)

            # Recompute edge from model output rather than trusting LLM arithmetic
            computed_edge = model_prob - market.probability

            trade_ok, direction = should_trade(signal)
            action = "TRADE" if trade_ok else "PASS"

            log = ReasoningLog(
                market_id=market.id,
                market_question=market.question,
                market_prob=market.probability,
                model_prob=model_prob,
                edge=round(computed_edge, 4),
                direction=direction if action == "TRADE" else "PASS",
                reasoning=reasoning,
                action_taken=action,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            save_reasoning_log(log)

            if action == "TRADE":
                trade = open_trade(market, signal, direction, reasoning)
                if trade:
                    print(
                        f"[loop]   *** TRADE {direction}: "
                        f"{market.question[:40]}... ${trade.stake_usd:.2f}"
                    )
        except Exception as e:
            print(f"[loop]   error on {market.id}: {e}")

    # Mark-to-market all open positions
    update_open_trades(list(market_map.values()))
    print("[loop] ── cycle done ──")


async def agent_loop():
    """Autonomous agent loop. Runs indefinitely in the background."""
    init_db()
    print(f"[agent] started — polling every {POLL_INTERVAL}s")

    while True:
        try:
            await _run_cycle()
        except Exception as e:
            print(f"[agent] unhandled cycle error: {e}")
        await asyncio.sleep(POLL_INTERVAL)
