from enum import Enum

from sqlmodel import SQLModel


class StatusType(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class StatusResponse(SQLModel):
    status: StatusType
    message: str | None = None
