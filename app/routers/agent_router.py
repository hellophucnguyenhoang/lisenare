from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
)
from app.services.agent.agent_core import run_agent
from app.services.agent.context import AgentContext

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/chat", response_model=AgentChatResponse)
def chat(
    body: AgentChatRequest,
    session: Session = Depends(get_session),
):
    ctx = AgentContext(session=session, learner_id=body.learner_id)
    result = run_agent(
        [m.model_dump() for m in body.messages],
        ctx,
    )
    return AgentChatResponse(**result)
