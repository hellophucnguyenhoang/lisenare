from sqlmodel import SQLModel


class ContextSearchRequest(SQLModel):
    query: str = "hang out"
