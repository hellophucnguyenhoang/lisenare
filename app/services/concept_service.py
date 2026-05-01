from sqlmodel import Session, select

from app.database import Concept, ConceptRelation, LessonConcept


def get_concept_by_id(session: Session, concept_id: int) -> Concept:
    statement = select(Concept).where(Concept.id == concept_id)
    result = session.exec(statement).first()
    return result


def get_concept_by_lesson_id(
    session: Session, lesson_id: int
) -> list[Concept]:
    statement = (
        select(Concept)
        .join(LessonConcept)
        .where(LessonConcept.lesson_id == lesson_id)
    )
    results = session.exec(statement)
    return results.all()


def get_child_concept_by_concept_id(
    session: Session, concept_id: int
) -> list[Concept]:
    statement = (
        select(Concept)
        .join(ConceptRelation, ConceptRelation.to_concept_id == Concept.id)
        .where(ConceptRelation.from_concept_id == concept_id)
    )
    results = session.exec(statement)
    return results.all()


def get_root_concept_by_lesson_id(
    session: Session, lesson_id: int
) -> list[Concept]:
    statement = select(Concept).where(
        ~Concept.id.in_(
            select(ConceptRelation.to_concept_id)
            .join(
                LessonConcept,
                ConceptRelation.to_concept_id == LessonConcept.concept_id,
            )
            .where(LessonConcept.lesson_id == lesson_id)
        )
    )
    results = session.exec(statement)
    return results.all()


def get_child_concept_by_concept_id(
    session: Session, concept_id: int
) -> list[Concept]:
    statement = (
        select(Concept)
        .join(ConceptRelation, ConceptRelation.to_concept_id == Concept.id)
        .where(ConceptRelation.from_concept_id == concept_id)
    )
    results = session.exec(statement)
    return results.all()


def get_father_concept_by_concept_id(
    session: Session, concept_id: int
) -> list[Concept]:
    statement = (
        select(Concept)
        .join(ConceptRelation, ConceptRelation.from_concept_id == Concept.id)
        .where(ConceptRelation.to_concept_id == concept_id)
    )
    results = session.exec(statement)
    return results.all()
