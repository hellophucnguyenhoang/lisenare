from sqlmodel import SQLModel


class OverrideCreateGroupsRequest(SQLModel):
    collection_ids: list[int]


class OverrideCreateDetail(SQLModel):
    cloned_collection_id: int
    created_count: int


class OverrideCreateGroupsResponse(SQLModel):
    total: int
    details: dict[int, OverrideCreateDetail]


class OverrideDeleteGroupsResponse(SQLModel):
    total: int
    details: dict[int, int]
