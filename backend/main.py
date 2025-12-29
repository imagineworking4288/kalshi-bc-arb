"""Main FastAPI application"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.websocket import websocket_endpoint
from .config import get_settings
from .database.connection import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await db.initialize()
    print("Database initialized")

    settings = get_settings()
    print(f"Running in {settings.kalshi_env.upper()} mode")
    print(f"API URL: {settings.kalshi_api_url}")

    yield

    # Shutdown
    print("Shutting down")


app = FastAPI(
    title="Kalshi Arbitrage Scanner",
    description="Detect and execute arbitrage opportunities on Kalshi",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router, prefix="/api")

# WebSocket endpoint
app.websocket("/ws")(websocket_endpoint)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Kalshi Arbitrage Scanner API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
