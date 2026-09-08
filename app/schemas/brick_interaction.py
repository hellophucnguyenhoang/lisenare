from enum import Enum

from sqlmodel import SQLModel


class InteractionType(str, Enum):
    LISTEN = "LISTEN"
    VIEW_TRANSLATION = "VIEW_TRANSLATION"
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"
    REMOVE_REACTION = "REMOVE_REACTION"
    ADD = "ADD"


class BrickInteractionCreate(SQLModel):
    session_id: str
    brick_id: int
    interaction_type: InteractionType
