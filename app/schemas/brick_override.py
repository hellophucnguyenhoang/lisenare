from sqlmodel import SQLModel


class OverrideBrickRequest(SQLModel):
    brick_id: int
    collection_name: str


class OverrideCollectionsCreateRequest(SQLModel):
    collection_ids: list[int]


class OverrideCreateDetail(SQLModel):
    cloned_collection_id: int
    created_count: int


class OverrideCollectionsCreateResponse(SQLModel):
    total: int
    details: dict[int, OverrideCreateDetail]


class OverrideCollectionsDeleteResponse(SQLModel):
    total: int
    details: dict[int, int]
