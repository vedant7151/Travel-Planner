from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.agents.graph import close_graph, init_graph
from app.api import trips, ws
from app.core.config import FRONTEND_ORIGIN
from app.core.llm import close_llm
from app.core.logging import logger
from app.core.rate_limit import api_limiter
from app.core.redis import close_redis
from app.db.postgres import close_pool, get_pool
from app.tools.client import close_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema migrations are applied out-of-band via the Supabase CLI
    # (see supabase/migrations/ and the README), not on every API boot.
    await init_graph()
    logger.info("travel planner API started")
    yield
    await close_graph()
    await close_pool()
    await close_http_client()
    await close_llm()
    await close_redis()


app = FastAPI(
    title="Travel Planner API",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = api_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = ["*"] if FRONTEND_ORIGIN == "*" else [FRONTEND_ORIGIN, "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router, prefix="/api/v1/trips")
app.include_router(ws.router, prefix="/ws")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc)},
    )


@app.get("/")
def read_root():
    return {"status": "ok", "service": "travel-planner"}


@app.get("/health")
async def health():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return {"status": "ok", "database": "up"}
    except Exception as exc:
        logger.exception("health check database failure")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "down", "detail": str(exc)},
        )
