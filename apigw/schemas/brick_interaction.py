from enum import Enum

from schemas.base import Schema


class InteractionType(str, Enum):
    LISTEN = "LISTEN"
    ADD = "ADD"


class BrickInteractionCreate(Schema):
    session_id: str
    brick_id: int
    interaction_type: InteractionType
