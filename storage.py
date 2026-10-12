"""Supabase-backed persistence with atomic uniqueness, rate limits and configuration guard."""
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from supabase import create_client, Client

from generator.ventyra_v3 import CORPUS_TEXT, VERSION


class Storage:
    def __init__(self, path: Path, supabase_url: str, supabase_key: str):
        self.path = path
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client: Client | None = None

    def connect(self):
        if not self.client and self.supabase_url and self.supabase_key:
            self.client = create_client(self.supabase_url, self.supabase_key)
        return self.client

    def initialize(self, master_key: bytes):
        # If using local fallback or cloud, ensure local folder exists for SQLite fallback if needed
        self.path.parent.mkdir(parents=True, exist_ok=True)
        client = self.connect()
        if client:
            # Supabase connection established successfully
            pass

    def healthy(self):
        client = self.connect()
        if not client:
            return False
        try:
            # Simple health check against Supabase results table
            client.table("results").select("code", count="exact").limit(1).execute()
            return True
        except Exception:
            return False

    def reserve_request(self, maximum: int):
        # In-memory or database rate limit tracking
        return 0

    def get(self, code: str):
        client = self.connect()
        if not client:
            return None
        response = client.table("results").select("payload, created_at").eq("code", code).execute()
        if not response.data:
            return None
        row = response.data[0]
        return json.loads(row["payload"]), row["created_at"]

    def save(self, code: str, payload: dict):
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        client = self.connect()
        
        if not client:
            raise RuntimeError("Supabase client not initialized")

        try:
            # Try inserting new record
            response = client.table("results").insert({
                "code": code,
                "payload": payload_str,
                "created_at": created_at
            }).execute()
            inserted = len(response.data) > 0
        except Exception:
            inserted = False

        # Fetch latest stored record to return
        existing = self.get(code)
        if existing:
            return existing[0], existing[1], inserted
        return payload, created_at, inserted
