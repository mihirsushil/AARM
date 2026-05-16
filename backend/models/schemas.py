from pydantic import BaseModel
from typing import Optional


class Market(BaseModel):
    id: str
    question: str
    probability: float
    volume: float
    liquidity: float
    category: str
    source: str = "polymarket"
    slug: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class RedditSignal(BaseModel):
    subreddit: str
    title: str
    sentiment: float       # -1 to 1
    relevance: float       # 0 to 1
    engagement_score: float
    upvotes: int
    comment_count: int
    created_at: str
    market_id: Optional[str] = None


class SignalResult(BaseModel):
    market_id: str
    sentiment_score: float      # weighted average sentiment
    narrative_velocity: float   # how fast discussion is growing
    divergence_score: float     # social consensus minus market price
    market_score: float         # combined signal strength
    edge: float                 # estimated_prob - market_prob
    confidence: float
    estimated_prob: float
    signal_count: int


class PaperTrade(BaseModel):
    id: Optional[int] = None
    market_id: str
    market_question: str
    side: str               # BUY or SELL
    entry_probability: float
    current_probability: float
    stake_usd: float
    pnl: float = 0.0
    status: str = "open"    # open or closed
    edge_at_entry: float
    confidence_at_entry: float
    reasoning: str
    opened_at: str
    closed_at: Optional[str] = None


class Portfolio(BaseModel):
    bankroll: float
    deployed: float
    available: float
    total_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    win_count: int
    loss_count: int
    win_rate: float
    open_trades: int
    total_trades: int


class ReasoningLog(BaseModel):
    id: Optional[int] = None
    market_id: str
    market_question: str
    market_prob: float
    model_prob: float
    edge: float
    direction: str
    reasoning: str
    action_taken: str   # TRADE or PASS
    timestamp: str
