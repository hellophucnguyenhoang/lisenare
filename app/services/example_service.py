from sqlmodel import Session, select

from app.database import Example, ExampleConcept


def get_example_by_id(session: Session, example_id: int) -> Example:
    statement = select(Example).where(Example.id == example_id)
    result = session.exec(statement).first()
    return result


def get_example_by_concept_id(
    session: Session, concept_id: int
) -> list[Example]:
    statement = (
        select(Example)
        .join(ExampleConcept)
        .where(ExampleConcept.concept_id == concept_id)
    )
    results = session.exec(statement)
    return results.all()
