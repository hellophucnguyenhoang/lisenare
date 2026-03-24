from sqlmodel import SQLModel


class InteractionCreate(SQLModel):
    post_id: int
    reward: float
