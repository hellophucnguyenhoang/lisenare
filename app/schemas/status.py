from enum import Enum

from sqlmodel import SQLModel


class StatusResponseType(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class StatusResponse(SQLModel):
    status: StatusResponseType
    message: str | None = None
