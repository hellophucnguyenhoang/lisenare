from enum import Enum

from sqlmodel import SQLModel


class InteractionType(str, Enum):
    LISTEN = "LISTEN"
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"
    REMOVE_REACTION = "REMOVE_REACTION"
    ADD = "ADD"
    TIME_SPENT = "TIME_SPENT"  # seconds


class SnippetInteractionCreate(SQLModel):
    session_id: str
    snippet_id: int
    interaction_type: InteractionType
    duration: float | None = None
