import sys
sys.path.append("..")

from shared.models import Market, SignalBundle
from reasoning.analyzer import analyze_market, save_trade

test_market = Market(
    id="fed-june-cut-2026",
    source="polymarket",
    title="Will the Fed cut rates in June 2026?",
    market_prob=0.38,
    volume=45000.0
)

test_signals = SignalBundle(
    market_id="fed-june-cut-2026",
    sentiment_delta=0.62,
    news_velocity=24,
    cross_market_avg=0.54,
    confidence=0.75
)

print("Analyzing market...")
decision = analyze_market(test_market, test_signals)

print(f"\n--- TRADE DECISION ---")
print(f"Market:     {test_market.title}")
print(f"Direction:  {decision.direction}")
print(f"Edge:       {decision.edge:+.1%}")
print(f"Model prob: {decision.model_prob:.1%} vs market {test_market.market_prob:.1%}")
print(f"Stake:      {decision.stake_pct:.1%} of bankroll")
print(f"Reasoning:  {decision.reasoning}")

if decision.direction != "PASS":
    save_trade(decision)
    print(f"\nTrade saved to aarm.db")