from sqlmodel import SQLModel


class OverrideGroupsCreate(SQLModel):
    group_names: list[str] = ["A1", "A2"]
    group_creator_id: int = 1


class OverrideGroupsResponse(SQLModel):
    total_created: int
    details: dict[str, int]
