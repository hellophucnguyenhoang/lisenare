from sqlmodel import Session, select

from app.database import BrokenBrickReport


def save_report(
    session: Session, filename: str, description: str | None = None
) -> BrokenBrickReport | None:
    # Check if the filename exists using a select statement
    statement = select(BrokenBrickReport).where(
        BrokenBrickReport.filename == filename
    )
    existing = session.exec(statement).first()
    if existing:
        return None

    new_report = BrokenBrickReport(filename=filename, description=description)
    session.add(new_report)
    session.commit()
    session.refresh(new_report)
    return new_report
