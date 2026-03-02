from sqlmodel import SQLModel


class StatusResponse(SQLModel):
    status: str
    message: str
