from app.database import get_session, Learner
from app.services import auth_service, collection_service
from app.schemas import CollectionCreate, CollectionRead
from schemas.cefr import CEFRLevel
from fastapi import APIRouter, Depends
from sqlmodel import Session

router = APIRouter(prefix="/collections", tags=["Collections"])

@router.get("", response_model=list[CollectionRead])
def get_learner_collections(
    group_name: str = CEFRLevel.A1,
    limit: int = 20, 
    page: int = 1,
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner), 
    session: Session = Depends(get_session)
):
    # Calculate offset: (page 1 - 1) * 20 = 0; (page 2 - 1) * 20 = 20
    offset = (page - 1) * limit
    return collection_service.get_user_collections(session, current_learner.id, group_name, limit, offset)

@router.post("", response_model=CollectionRead)
def create_learner_collection(
    collection_create: CollectionCreate,
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner), 
    session: Session = Depends(get_session)
):
    return collection_service.create_collection(
        session=session, 
        learner_id=current_learner.id, 
        collection_create=collection_create
    )
