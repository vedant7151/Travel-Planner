import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env", override=True)


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "").strip()
LANGCHAIN_TRACING_V2 = _bool("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "travel-planner")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
REDIS_URL = os.getenv("REDIS_URL", "").strip().strip('"')
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip().strip('"')
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip().strip('"')
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
SUPABASE_JWKS_URL = os.getenv(
    "SUPABASE_JWKS_URL",
    f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else "",
).strip()
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
HTTP_RETRY_ATTEMPTS = int(os.getenv("HTTP_RETRY_ATTEMPTS", "3"))
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "TravelPlanner/1.0 (educational; https://github.com/travel-planner)",
).strip()
NOMINATIM_EMAIL = os.getenv("NOMINATIM_EMAIL", "").strip()
NOMINATIM_BASE_URL = os.getenv(
    "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"
).rstrip("/")
NOMINATIM_RESULT_LIMIT = int(os.getenv("NOMINATIM_RESULT_LIMIT", "8"))
OPEN_METEO_BASE_URL = os.getenv(
    "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"
).rstrip("/")
OSRM_BASE_URL = os.getenv(
    "OSRM_BASE_URL", "https://router.project-osrm.org"
).rstrip("/")
DDG_MAX_RESULTS = int(os.getenv("DDG_MAX_RESULTS", "8"))
DDG_REGION = os.getenv("DDG_REGION", "wt-wt").strip() or "wt-wt"
GROQ_TPM_LIMIT = int(os.getenv("GROQ_TPM_LIMIT", "10000"))
GEMINI_RPM_LIMIT = int(os.getenv("GEMINI_RPM_LIMIT", "10"))
GROQ_RATE_LIMIT = max(1, int(GROQ_TPM_LIMIT * 0.8))
GEMINI_RATE_LIMIT = max(1, int(GEMINI_RPM_LIMIT * 0.8))

_raw_db = os.getenv("DATABASE_URL", "")
_raw_system_db = os.getenv("SYSTEM_DATABASE_URL", _raw_db)


def _normalize_db_url(url: str) -> str:
    if not url:
        return ""
    cleaned = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    cleaned = cleaned.replace("postgres://", "postgresql://", 1)
    return cleaned


DATABASE_URL = _normalize_db_url(_raw_db)
SYSTEM_DATABASE_URL = _normalize_db_url(_raw_system_db)


def asyncpg_dsn(url: str | None = None) -> str:
    """DSN for asyncpg (query sslmode is stripped; SSL is passed separately)."""
    raw = url or DATABASE_URL
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)
    qs.pop("sslmode", None)
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    return urlunparse(parsed._replace(query=new_query))


def asyncpg_connect_kwargs(url: str | None = None) -> dict[str, object]:
    """Return parsed asyncpg arguments for Supabase pooler URLs."""
    parsed = urlparse(asyncpg_dsn(url))
    return {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
    }


def system_database_url() -> str:
    if not SYSTEM_DATABASE_URL:
        raise RuntimeError(
            "SYSTEM_DATABASE_URL is not set. Configure a privileged Supabase "
            "connection for migrations, LangGraph, and system tables."
        )
    return SYSTEM_DATABASE_URL


def psycopg_conninfo(url: str | None = None) -> str:
    raw = url or DATABASE_URL
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)
    if "sslmode" not in qs:
        qs["sslmode"] = ["require"]
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    username = quote(unquote(parsed.username or ""), safe="")
    password = quote(unquote(parsed.password or ""), safe="")
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{username}:{password}@{host}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc, query=new_query))


if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if LANGCHAIN_TRACING_V2 else "false"
