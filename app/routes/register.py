import os
import hmac
import hashlib
import secrets
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import supabase

router = APIRouter()

API_KEY_SECRET = os.environ.get("API_KEY_SECRET", "")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str


def hash_key(raw_key: str) -> str:
    return hmac.new(
        API_KEY_SECRET.encode(),
        raw_key.encode(),
        hashlib.sha256,
    ).hexdigest()


@router.post("/register")
def register(body: RegisterRequest):
    if not EMAIL_RE.match(body.email):
        raise HTTPException(status_code=422, detail="Invalid email format")

    existing = (
        supabase.table("api_keys")
        .select("id")
        .eq("email", body.email)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")

    raw_key = secrets.token_urlsafe(32)
    key_hash = hash_key(raw_key)

    supabase.table("api_keys").insert(
        {"email": body.email, "key_hash": key_hash}
    ).execute()

    return {
        "api_key": raw_key,
        "message": "Store this key safely. It will not be shown again.",
        "rate_limit": "100 requests/day",
    }
