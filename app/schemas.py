from sqlmodel import SQLModel

class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    is_public: bool | None = None
