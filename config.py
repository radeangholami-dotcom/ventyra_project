"""Validated environment configuration; no production secrets in source."""
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    master_key: bytes
    api_key: str
    database_path: Path
    supabase_url: str
    supabase_key: str
    environment: str = "development"
    cors_origins: tuple[str, ...] = ()
    requests_per_minute: int = 120

    @classmethod
    def from_env(cls):
        secret = os.getenv("VENTYRA_MASTER_KEY", "")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", secret):
            raise ValueError("VENTYRA_MASTER_KEY must be 64 hexadecimal characters")
        key = os.getenv("VENTYRA_API_KEY", "")
        if len(key) < 32 or not key.isascii() or any(c.isspace() for c in key):
            raise ValueError("VENTYRA_API_KEY must have at least 32 ASCII characters without whitespace")
        
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_KEY", "")
        
        environment = os.getenv("VENTYRA_ENV", "development")
        if environment not in {"development", "production"}:
            raise ValueError("VENTYRA_ENV must be development or production")
        origins = tuple(x.strip() for x in os.getenv("VENTYRA_CORS_ORIGINS", "").split(",") if x.strip())
        if any(not re.fullmatch(r"https?://[^/\s]+", origin) for origin in origins):
            raise ValueError("CORS origins must be explicit http(s) origins without trailing slash")
        limit = int(os.getenv("VENTYRA_REQUESTS_PER_MINUTE", "120"))
        if not 1 <= limit <= 100000:
            raise ValueError("Request limit must be between 1 and 100000")
        path = Path(os.getenv("VENTYRA_DATABASE_PATH", "./data/ventyra.sqlite3"))
        return cls(bytes.fromhex(secret), key, path, supabase_url, supabase_key, environment, origins, limit)
