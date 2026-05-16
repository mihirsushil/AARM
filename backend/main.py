import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.loop import agent_loop
from backend.api import markets, trades, portfolio, signals, reasoning


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(agent_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="AARM API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets.router)
app.include_router(trades.router)
app.include_router(portfolio.router)
app.include_router(signals.router)
app.include_router(reasoning.router)


@app.get("/")
def health():
    return {"status": "ok", "system": "AARM"}
