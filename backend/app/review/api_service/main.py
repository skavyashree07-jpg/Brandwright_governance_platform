from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .database import init_db
from .router import router

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title=settings.app_name, version="1.0.0",
              description="Standalone API adapter for Brandwright's AI & Review Engine.",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "brandwright-ai-review-engine"}

@app.get("/", tags=["Health"])
def root():
    return {"service": settings.app_name, "docs": "/docs", "health": "/health"}

app.include_router(router)
