import os
import hmac
import hashlib
from datetime import date
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.db import supabase

SKIP_PATHS = {"/", "/docs", "/openapi.json", "/v1/register"}
API_KEY_SECRET = os.environ.get("API_KEY_SECRET", "")


def hash_key(raw_key: str) -> str:
    return hmac.new(
        API_KEY_SECRET.encode(),
        raw_key.encode(),
        hashlib.sha256,
    ).hexdigest()


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        raw_key = request.headers.get("x-api-key")
        if not raw_key:
            return JSONResponse({"detail": "Missing API key"}, status_code=401)

        key_hash = hash_key(raw_key)

        key_row = (
            supabase.table("api_keys")
            .select("id, is_active")
            .eq("key_hash", key_hash)
            .limit(1)
            .execute()
        )
        if not key_row.data or not key_row.data[0].get("is_active"):
            return JSONResponse({"detail": "Invalid or inactive API key"}, status_code=401)

        today = date.today().isoformat()
        count_row = (
            supabase.table("request_counts")
            .select("id, count")
            .eq("key_hash", key_hash)
            .eq("date", today)
            .limit(1)
            .execute()
        )

        if count_row.data:
            current = count_row.data[0]
            current_count = current["count"]
            if current_count >= 100:
                return JSONResponse(
                    {"detail": "Rate limit exceeded. 100 requests/day."},
                    status_code=429,
                )
            supabase.table("request_counts").update({"count": current_count + 1}).eq(
                "id", current["id"]
            ).execute()
        else:
            supabase.table("request_counts").upsert(
                {"key_hash": key_hash, "date": today, "count": 1},
                on_conflict="key_hash,date",
            ).execute()

        request.state.key_hash = key_hash
        return await call_next(request)
