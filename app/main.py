import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.mongo import ensure_indexes
from app.routers import auth, analysis, profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CompliancePilot backend")
    await ensure_indexes()
    logger.info("MongoDB indexes ensured")
    logger.info("CompliancePilot backend ready")
    yield
    logger.info("CompliancePilot backend shutting down")

app = FastAPI(
    title="CompliancePilot API",
    description="AI-powered document compliance analysis backend",
    version="2.0.0",
    lifespan=lifespan,
    redoc_url=None if settings.app_env == "production" else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "X-Accel-Buffering"],
)

app.include_router(auth.router)
app.include_router(analysis.router)
app.include_router(profile.router)

@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )