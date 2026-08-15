from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.batch import router as batch_router
from app.api.v1.overview import router as overview_router
from app.api.v1.report import router as report_router
from app.api.v1.transactions import router as transactions_router
from app.core.dependencies import get_current_bank_client, get_current_user
from app.models.bank_client import BankClient
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.bank_client import BankClientOut

app = FastAPI(title="VALLI SecurePay AI", version="0.1.0")

# Dev-only: the React frontend's webpack-dev-server runs on 5173. A real
# deployment should read allowed origins from settings instead of hardcoding
# the local dev port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/v1")
# batch_router and report_router registered before transactions_router:
# transactions_router's GET /{transaction_id} is broad enough to shadow
# single-segment routes under the same /transactions prefix (report_router's
# GET /transactions and GET /transactions/export) if it were registered
# first. overview_router/admin_router have distinct prefixes, no collision
# risk, but kept alongside for consistency.
app.include_router(batch_router, prefix="/v1")
app.include_router(report_router, prefix="/v1")
app.include_router(overview_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1")
app.include_router(transactions_router, prefix="/v1")


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


@app.get("/v1/me/bank", response_model=BankClientOut)
def me_bank(current_client: BankClient = Depends(get_current_bank_client)) -> BankClientOut:
    """Proves the X-API-Key path works end-to-end; the bank simulator can
    hit this to confirm its key is valid before calling the scoring API."""
    return BankClientOut.model_validate(current_client)
