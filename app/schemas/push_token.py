from sqlmodel import SQLModel


class PushTokenRegister(SQLModel):
    token: str
    device_name: str | None = "Unknown Device"
