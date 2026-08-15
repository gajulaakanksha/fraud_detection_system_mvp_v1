import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

API_KEY_PREFIX = "vsp_"


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str, role: str) -> tuple[str, int]:
    expires_in = settings.jwt_expire_minutes * 60
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    payload = {"sub": subject, "role": role, "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def generate_api_key() -> str:
    """Raw key shown to the caller exactly once at issuance time; only its
    hash is ever persisted."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    # API keys are high-entropy, randomly generated secrets (unlike
    # passwords), so a fast deterministic hash is appropriate here -- bcrypt
    # is for defending low-entropy, human-chosen secrets against brute force.
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
