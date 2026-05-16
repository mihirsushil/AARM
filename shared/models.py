from dataclasses import dataclass

@dataclass
class Market:
    id: str
    source: str
    title: str
    market_prob: float
    volume: float = 0.0
    closes_at: str = ""

@dataclass
class SignalBundle:
    market_id: str
    sentiment_delta: float
    news_velocity: float
    cross_market_avg: float
    confidence: float = 0.7

@dataclass
class TradeDecision:
    market_id: str
    edge: float
    direction: str
    stake_pct: float
    reasoning: str
    model_prob: float = 0.0