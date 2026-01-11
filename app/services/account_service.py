from app.database import Account, Learner
from app.schemas import LearnerAccountCreate
from app import security
from sqlmodel import select, Session

def get_account_by_username(session: Session, username: str) -> Account:
    statement = select(Account).where(Account.username == username)
    return session.exec(statement).first()

def create_learner_account(session: Session, learner_account_create: LearnerAccountCreate) -> Account:
    learner = Learner(full_name=learner_account_create.full_name)

    hashed_password = security.get_password_hash(learner_account_create.password)
    account = Account(
        username=learner_account_create.username,
        hashed_password=hashed_password,
        email=learner_account_create.email,
        learner=learner
    )

    session.add(account)
    session.commit()
    session.refresh(account)
    return account
