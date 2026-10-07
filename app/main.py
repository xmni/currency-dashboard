from fastapi import FastAPI

from app.core.config import settings
from app.market.router import router as market_router

app = FastAPI(title=settings.app_name)
app.include_router(market_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}