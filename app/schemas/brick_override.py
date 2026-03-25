from sqlmodel import SQLModel
from . import CEFRLevel


class OverrideGroupsCreate(SQLModel):
    group_names: list[CEFRLevel] = [CEFRLevel.A1, CEFRLevel.A2]
    group_creator_id: int = 1


class OverrideGroupsResponse(SQLModel):
    total_created: int
    details: dict[str, int]
