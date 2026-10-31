from enum import Enum

from sqlmodel import SQLModel


class InteractionType(str, Enum):
    LISTEN = "LISTEN"
    ADD = "ADD"


class BrickInteractionCreate(SQLModel):
    session_id: str
    brick_id: int
    interaction_type: InteractionType
