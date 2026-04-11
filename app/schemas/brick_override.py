from sqlmodel import SQLModel

from schemas.cefr import CEFR_MAPPING


class OverrideGroupsCreate(SQLModel):
    group_names: list[str] = list(CEFR_MAPPING.values())
    group_creator_id: int = 1


class OverrideGroupsResponse(SQLModel):
    total_created: int
    details: dict[str, int]
