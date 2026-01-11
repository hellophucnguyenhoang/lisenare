from app.database import get_session, Learner
from app.services import auth_service, collection_service
from app.schemas import CollectionCreate, CollectionRead
from fastapi import APIRouter, Depends
from sqlmodel import Session

router = APIRouter(prefix="/collections", tags=["Collections"])

@router.get("", response_model=list[CollectionRead])
async def get_learner_collections(
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner), 
    session: Session = Depends(get_session)
):
    return collection_service.get_user_collections(session, current_learner.id)

@router.post("")
async def create_learner_collection(
    collection_create: CollectionCreate,
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner), 
    session: Session = Depends(get_session)
):
    return collection_service.create_collection(
        session=session, 
        learner_id=current_learner.id, 
        collection_name=collection_create.name
    )
