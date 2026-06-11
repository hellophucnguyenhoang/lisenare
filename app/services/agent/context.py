from dataclasses import dataclass

from sqlmodel import Session


@dataclass
class AgentContext:
    session: Session
    learner_id: int
