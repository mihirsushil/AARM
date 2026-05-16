import os
from datetime import datetime, timezone
from backend.models.schemas import RedditSignal

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

SUBREDDITS = [
    "politics", "worldnews", "economics",
    "technology", "wallstreetbets", "cryptocurrency", "singularity",
]

_POSITIVE_WORDS = {
    "likely", "yes", "win", "up", "bull", "positive", "strong",
    "good", "great", "rise", "gain", "surge", "pass", "approve",
}
_NEGATIVE_WORDS = {
    "unlikely", "no", "fail", "down", "bear", "negative", "weak",
    "bad", "crash", "drop", "lose", "reject", "deny", "fall",
}


def _simple_sentiment(text: str) -> float:
    words = set(text.lower().split())
    pos = len(words & _POSITIVE_WORDS)
    neg = len(words & _NEGATIVE_WORDS)
    total = pos + neg
    return (pos - neg) / total if total > 0 else 0.0


def _get_client():
    if not PRAW_AVAILABLE:
        return None
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=os.getenv("REDDIT_USER_AGENT", "aarm/1.0"),
    )


def fetch_reddit_signals(
    market_question: str,
    market_id: str,
    limit_per_sub: int = 8,
) -> list[RedditSignal]:
    reddit = _get_client()
    if not reddit:
        return []

    # Use first 4 content words as search query
    query = " ".join(w for w in market_question.split()[:6] if len(w) > 3)
    signals: list[RedditSignal] = []

    for sub_name in SUBREDDITS[:4]:
        try:
            sub = reddit.subreddit(sub_name)
            for post in sub.search(query, limit=limit_per_sub, sort="hot", time_filter="week"):
                text = post.title + " " + (post.selftext[:300] if post.selftext else "")
                sentiment = _simple_sentiment(text)
                engagement = min(1.0, (post.score + post.num_comments * 5) / 1000)
                relevance = min(1.0, post.score / 500)

                signals.append(RedditSignal(
                    subreddit=sub_name,
                    title=post.title,
                    sentiment=sentiment,
                    relevance=relevance,
                    engagement_score=engagement,
                    upvotes=post.score,
                    comment_count=post.num_comments,
                    created_at=datetime.fromtimestamp(
                        post.created_utc, tz=timezone.utc
                    ).isoformat(),
                    market_id=market_id,
                ))
        except Exception as e:
            print(f"[reddit] r/{sub_name} error: {e}")
            continue

    return signals
