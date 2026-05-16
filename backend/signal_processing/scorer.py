from backend.models.schemas import Market, RedditSignal, SignalResult

MAX_LIQUIDITY = 500_000.0


def _sentiment_score(signals: list[RedditSignal]) -> float:
    if not signals:
        return 0.0
    weight_sum = sum(s.relevance * s.engagement_score for s in signals)
    if weight_sum == 0:
        return 0.0
    return sum(s.sentiment * s.relevance * s.engagement_score for s in signals) / weight_sum


def _narrative_velocity(signals: list[RedditSignal]) -> float:
    if not signals:
        return 0.0
    return min(1.0, sum(s.engagement_score for s in signals) / max(1, len(signals)))


def _liquidity_factor(liquidity: float) -> float:
    if liquidity <= 0:
        return 0.3
    return min(1.0, liquidity / MAX_LIQUIDITY)


def _sentiment_variance(signals: list[RedditSignal], mean: float) -> float:
    if len(signals) < 2:
        return 0.0
    return sum((s.sentiment - mean) ** 2 for s in signals) / len(signals)


def score_market(market: Market, signals: list[RedditSignal]) -> SignalResult:
    sentiment = _sentiment_score(signals)
    velocity = _narrative_velocity(signals)
    liq_factor = _liquidity_factor(market.liquidity)

    # Map sentiment [-1, 1] → probability shift, capped to ±0.4
    social_prob = max(0.01, min(0.99, 0.5 + sentiment * 0.4))
    divergence = social_prob - market.probability

    market_score = min(1.0, max(0.0,
        abs(sentiment) * 0.30
        + velocity * 0.20
        + abs(divergence) * 0.30
        + liq_factor * 0.20
    ))

    # Weight estimated probability toward social signal based on signal count
    signal_weight = min(1.0, len(signals) / 20)
    estimated_prob = max(0.01, min(0.99,
        market.probability + divergence * signal_weight * 0.5
    ))

    edge = estimated_prob - market.probability

    variance = _sentiment_variance(signals, sentiment)
    confidence = max(0.1, min(0.95,
        signal_weight * 0.50
        + (1.0 - variance) * 0.30
        + liq_factor * 0.20
    ))

    return SignalResult(
        market_id=market.id,
        sentiment_score=round(sentiment, 4),
        narrative_velocity=round(velocity, 4),
        divergence_score=round(divergence, 4),
        market_score=round(market_score, 4),
        edge=round(edge, 4),
        confidence=round(confidence, 4),
        estimated_prob=round(estimated_prob, 4),
        signal_count=len(signals),
    )
