import uuid

from pydantic import BaseModel


class BankClientOut(BaseModel):
    id: uuid.UUID
    bank_name: str
    bank_code: str

    model_config = {"from_attributes": True}
