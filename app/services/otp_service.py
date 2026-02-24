from sqlmodel import Session
from app.database import OTP
from app import security

def create_otp(
    session: Session,
    email: str,
) -> None:
    code = security.generate_otp()
    db_otp = OTP(
        email=email,
        hashed_code=security.hash_code(code)
    )
    session.add(db_otp)
    session.commit()
    return code
