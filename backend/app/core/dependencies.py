import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, hash_api_key
from app.db.session import get_db
from app.models.bank_client import BankClient
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "unauthorized", "message": detail}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise _unauthorized("Invalid or expired token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Admin role required"}},
        )
    return user


def get_current_bank_client(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> BankClient:
    """Auth for machine callers (a bank's backend hitting the scoring/batch
    API directly) as opposed to get_current_user, which authenticates a
    human analyst session in the console via JWT."""
    if not x_api_key:
        raise _unauthorized("Missing X-API-Key header")

    client = db.query(BankClient).filter(BankClient.api_key_hash == hash_api_key(x_api_key)).one_or_none()
    if client is None or not client.is_active:
        raise _unauthorized("Invalid or revoked API key")
    return client


@dataclass
class Caller:
    """Discriminated identity for endpoints two different kinds of callers
    can hit: an analyst's browser session (JWT) or a bank's backend (API
    key). actor_type drives audit-log attribution and Transaction.source."""
    actor_type: str  # "analyst" | "bank_client"
    user: User | None = None
    bank_client: BankClient | None = None


def get_current_caller(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Caller:
    """Scoring/batch endpoints accept either an analyst JWT or a bank's
    X-API-Key -- the same two auth paths as get_current_user /
    get_current_bank_client, unified so a single endpoint can serve both the
    console UI and a bank's integration without duplicating the route."""
    if x_api_key:
        client = db.query(BankClient).filter(BankClient.api_key_hash == hash_api_key(x_api_key)).one_or_none()
        if client is None or not client.is_active:
            raise _unauthorized("Invalid or revoked API key")
        return Caller(actor_type="bank_client", bank_client=client)

    if credentials:
        try:
            payload = decode_access_token(credentials.credentials)
            user_id = uuid.UUID(payload["sub"])
        except (ValueError, KeyError):
            raise _unauthorized("Invalid or expired token")
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            raise _unauthorized("User not found or inactive")
        return Caller(actor_type="analyst", user=user)

    raise _unauthorized("Provide either a Bearer token or an X-API-Key header")
