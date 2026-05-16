from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import dataclasses
from reasoning.analyzer import analyze_market, get_all_trades, save_trade
from shared.models import Market, SignalBundle

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health():
    return {"status": "ok", "system": "AARM"}

@app.get("/analyze/{market_id}")
def analyze(market_id: str):
    market = Market(
        id=market_id,
        source="manifold",
        title=f"Market {market_id}",
        market_prob=0.45,
        volume=10000.0
    )
    signals = SignalBundle(
        market_id=market_id,
        sentiment_delta=0.3,
        news_velocity=12,
        cross_market_avg=0.51,
        confidence=0.7
    )
    decision = analyze_market(market, signals)
    if decision.direction != "PASS":
        save_trade(decision)
    return dataclasses.asdict(decision)

@app.get("/trades")
def trades():
    return get_all_trades()