from sqlmodel import SQLModel

class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(SQLModel):
    sub: str # learner_id, store as string for required
    username: str
    exp: int
    
class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    is_public: bool | None = None
    collection_ids: list[int] | None = None

class LearnerAccountCreate(SQLModel):
    full_name: str
    username: str
    password: str
    email: str | None = None
